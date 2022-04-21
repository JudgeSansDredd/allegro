import http.client
import json

from allegrosettings import TEMPO_TOKEN
from timesheets.timesheet import DayTimeSheet, IssueTimeSheet, TimeSheet

from ..interface import TimeKeepingInterface


class TempoAccess(TimeKeepingInterface):
    def __init__(self, token=TEMPO_TOKEN):
        self.token = token

    def _getWorkDays(self, start, end):
        conn = http.client.HTTPSConnection("api.tempo.io")
        headersList = {
        "Accept": "*/*",
        "User-Agent": "Allegro Python Script",
        "Authorization": f"Bearer {self.token}"
        }

        payload = ""

        strStart = f"{start.year}-{start.month}-{start.day}"
        strEnd = f"{end.year}-{end.month}-{end.day}"

        conn.request(
            "GET",
            f"/core/3/user-schedule?from={strStart}&to={strEnd}",
            payload,
            headersList
        )
        response = conn.getresponse()
        result = response.read()

        parsed = json.loads(result.decode('utf-8'))
        days = parsed['results']
        return [
            {
                'date': day['date'],
                'required': day['requiredSeconds']
            }
            for day in days
            if day['type'].upper() == 'WORKING_DAY'
        ]

    def getWorkByDay(self, start, end, userId):
        conn = http.client.HTTPSConnection("api.tempo.io")

        headersList = {
        "Accept": "*/*",
        "User-Agent": "Allegro Python Script",
        "Authorization": f"Bearer {self.token}"
        }

        payload = ""

        strStart = f"{start.year}-{start.month}-{start.day}"
        strEnd = f"{end.year}-{end.month}-{end.day}"

        conn.request(
            "GET",
            f"/core/3/worklogs/user/{userId}?from={strStart}&to={strEnd}",
            payload,
            headersList
        )
        response = conn.getresponse()
        result = response.read()
        parsed = json.loads(result.decode('utf-8'))
        worklogs = parsed['results']

        dates = self._getWorkDays(start, end)
        workByDate = {}
        workByIssue = {}

        for d in dates:
            dateWorklogs = [log for log in worklogs if log['startDate'] == d['date']]
            byKey = {}
            for log in dateWorklogs:
                if log['issue']['key'] not in byKey:
                    byKey[log['issue']['key']] = log['timeSpentSeconds']
                else:
                    byKey[log['issue']['key']] += log['timeSpentSeconds']
            workByDate[d['date']] = (DayTimeSheet(d['date'], d['required'], byKey))
            for issue, time in byKey.items():
                if issue not in workByIssue:
                    workByIssue[issue] = IssueTimeSheet(issue, time)
                else:
                    workByIssue[issue].addWork(time)
        return TimeSheet(workByDate, workByIssue)

    def submitTime(self, submission, userId):
        issue = submission['issue']
        day = submission['day']
        timeSpent = submission['timeSpent']

        if timeSpent == 0:
            return

        print(f'Submitting {timeSpent / 3600} for {issue} on {day}... ', end='')

        conn = http.client.HTTPSConnection("api.tempo.io")

        headersList = {
        "Accept": "*/*",
        "User-Agent": "Allegro Python Script",
        "Authorization": f"Bearer {self.token}",
        "Content-Type": "application/json"
        }

        params = {
            'issueKey': issue,
            'timeSpentSeconds': timeSpent,
            'startDate': day,
            'startTime': '12:00:00',
            'authorAccountId': userId
        }

        conn.request(
            "POST",
            "/core/3/worklogs",
            json.dumps(params),
            headersList
        )
        conn.getresponse()

        print('Done')
