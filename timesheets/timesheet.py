import json


class TimeSheet():
    def __init__(self, dayTimeSheets, issueTimeSheets):
        self.requiredPerIssue = None
        self.dayTimeSheets = dayTimeSheets
        self.issueTimeSheets = issueTimeSheets

    def setRequiredPerIssue(self, time):
        self.requiredPerIssue = time

    def getDays(self):
        return self.dayTimeSheets.keys()

    def getTotalNeeded(self, issues):
        required = sum([
            sheet.required
            for sheet in self.dayTimeSheets.values()
        ])
        worked   = sum([
            sheet.getWorkedMisc(issues)
            for sheet in self.dayTimeSheets.values()
        ])
        needed = required - worked
        return needed if needed > 0 else 0

    def addWork(self, day, issue, time):
        self.dayTimeSheets[day].addWork(issue, time)
        if issue in self.issueTimeSheets:
            self.issueTimeSheets[issue].addWork(time)
        else:
            self.issueTimeSheets[issue] = IssueTimeSheet(issue, time)

    def getAllowedWork(self, day, issue):
        if self.requiredPerIssue is None:
            raise Exception('You have not set the required per issue variable')
        dayNeeded = self.dayTimeSheets[day].needed
        if issue in self.issueTimeSheets:
            issueWorked = self.issueTimeSheets[issue].worked
        else:
            issueWorked = 0
        issueNeeded = self.requiredPerIssue - issueWorked
        allowed = min(dayNeeded, issueNeeded)
        return allowed if allowed > 0 else 0


class IssueTimeSheet():
    def __init__(self, issue, worked):
        self.issue = issue
        self.worked = worked

    def addWork(self, time):
        self.worked += time

class DayTimeSheet():
    def __init__(self, day, required, worklogs):
        self.day = day
        self.required = required
        self.worklogs = worklogs
        self._calcDayData()

    def __str__(self):
        out = {
            'date': self.day,
            'required': self.required,
            'worked': self.worked,
            'needed': self.needed,
            'worklogs': self.worklogs
        }
        return json.dumps(out, indent=4)

    def __repr__(self):
        return self.__str__()

    def addWork(self, issue, time):
        if issue in self.worklogs:
            current = self.worklogs[issue]
            new = current + time
            self.worklogs[issue] = new
        else:
            self.worklogs[issue] = time
        self._calcDayData()

    def getWork(self, issue):
        return self.worklogs[issue] if issue in self.worklogs else 0

    def _calcDayData(self):
        self.worked = sum(self.worklogs.values())
        self.needed = self.required - self.worked

    def getWorkedMisc(self, issues):
        return sum([
            worklog
            for issue, worklog
            in self.worklogs.items()
            if issue not in issues
        ])
