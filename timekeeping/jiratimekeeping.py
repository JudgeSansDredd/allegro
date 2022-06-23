import time
from configparser import ConfigParser
from datetime import datetime, timedelta

import pytz
from jira import JIRA

from timesheets.timesheet import DayTimeSheet, IssueTimeSheet, TimeSheet


class JiraTimekeeping():
    def __init__(self, configPath):
        config = ConfigParser()
        config.read(configPath)
        self.emailAddress = config.get('JIRA', 'EMAIL_ADDRESS')
        self.jira = JIRA(
            {'server': config.get('JIRA', 'JIRA_SERVER')},
            basic_auth=(
                config.get('JIRA', 'EMAIL_ADDRESS'),
                config.get('JIRA', 'JIRA_KEY')
            )
        )
        self.projectId = self.jira.project(config.get('JIRA', 'PROJECT_KEY')).id
        self.percentWorkedPerDay = int(config.get(
            'ALLEGRO',
            'PERCENT_WORKED_PER_DAY'
        ))

        self.timezone = pytz.timezone(config.get('ALLEGRO', 'TIMEZONE'))
    def _getWorkDays(self, start, end):
        # TODO: Account for holidays
        return [
            {
                'date': (start + timedelta(days=i)).isoformat(),
                'required': int(8 * 3600 * (self.percentWorkedPerDay / 100))
            }
            for i
            in range((end - start).days + 1)
            if (start + timedelta(days=i)).isoweekday() > 0
            and (start + timedelta(days=i)).isoweekday() < 6
        ]
    def getWorkByDay(self, start, end):
        issues = self.jira.search_issues(
            f"project={self.projectId} AND Sprint in openSprints()",
            maxResults=1000
        )

        allWorklogsByIssue = [
            self.jira.worklogs(issue.key)
            for issue in issues
        ]
        worklogs = [
            worklog
            for worklogsForIssue in allWorklogsByIssue
            for worklog in worklogsForIssue
            if worklog.author.emailAddress.lower() == self.emailAddress.lower()
        ]

        dates = self._getWorkDays(start, end)
        workByDate = {}
        workByIssue = {}

        for d in dates:
            dateWorklogs = [
                log
                for log in worklogs
                if log.started.split('T')[0] == d['date']
            ]
            byKey = {}
            for log in dateWorklogs:
                issueKey = self.jira.issue(log.issueId).key
                if issueKey not in byKey:
                    byKey[issueKey] = log.timeSpentSeconds
                else:
                    byKey[issueKey] += log.timeSpentSeconds
            workByDate[d['date']] = (DayTimeSheet(d['date'], d['required'], byKey))
            for issue, time in byKey.items():
                if issue not in workByIssue:
                    workByIssue[issue] = IssueTimeSheet(issue, time)
                else:
                    workByIssue[issue].addWork(time)
        return TimeSheet(workByDate, workByIssue)

    def submitTime(self, submission):
        issue = submission['issue']
        day = submission['day']
        timeSpent = submission['timeSpent']

        if timeSpent == 0:
            return

        print(f'Submitting {timeSpent / 3600} for {issue} on {day}... ', end='')

        naiveDateTime = datetime.fromisoformat(day)
        localDateTime = self.timezone.localize(
            naiveDateTime,
            time.localtime().tm_isdst
        )

        # Add 12 hours so we log time at noon
        localDateTime += timedelta(hours=12)

        # NOTE: I don't know why, but Jira insists that I'm 2 hours further
        # back from UTC than I actually am. I'm adding two hours to the start
        # date so that the hours worked still show up on the correct day
        localDateTime += timedelta(hours=2)

        # NOTE: We're making the assumption that the largest time will be less than one day
        params = {
            "issue": issue,
            "started": localDateTime,
            "timeSpentSeconds": timeSpent,
            "newEstimate": "0m"
        }
        self.jira.add_worklog(**params)

        print('Done')
