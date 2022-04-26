from jira import JIRA

from allegrosettings import EMAIL_ADDRESS, JIRA_KEY, JIRA_SERVER, PROJECT_KEY


class JiraAccess():
    def __init__(
        self,
        server=JIRA_SERVER,
        emailAddress=EMAIL_ADDRESS,
        token=JIRA_KEY,
        projectKey=PROJECT_KEY
    ):
        self.jira = JIRA({'server': server}, basic_auth=(emailAddress, token))
        self.projectId = self.jira.project(projectKey).id

    def getAccountId(self) -> str:
        return self.jira.myself()['accountId']

    def getAllSubtasks(self, issueKeys) -> list[str]:
        issues = self.getIssues(issueKeys)
        allFilteredSubtasks = []
        for issue in issues:
            subtasks = [
                st.key
                for st
                in self._getSubtasksAsIssues(issue)
                if st.fields.assignee is not None
                and st.fields.assignee.emailAddress.lower() == EMAIL_ADDRESS.lower()
            ]
            subtasks.reverse()
            allFilteredSubtasks.extend(subtasks)
        return allFilteredSubtasks

    def _getSubtasksAsIssues(self, parentIssue):
        # Grab the subtasks
        subtaskIds = [subtask.key for subtask in parentIssue.fields.subtasks]
        return self.getIssues(subtaskIds) if subtaskIds else []

    def getIssues(self, issueKeys: list[str]):
        keyString = ', '.join([f'\"{key}\"' for key in issueKeys])
        keyQuery = f"key IN ({keyString})"
        sprintQuery = f"project={self.projectId} AND Sprint in openSprints()"
        sprintQuery += " AND Assignee = currentUser()"
        if len(issueKeys) > 0:
            queryString = f"({keyQuery}) OR ({sprintQuery})"
        else:
            queryString = sprintQuery
        return self.jira.search_issues(
            queryString,
            maxResults=False
        )

    def getIssuesForMenu(self):
        queryString = f"project={self.projectId} AND Sprint in openSprints()"
        return self.jira.search_issues(queryString, maxResults=False)
