from configparser import ConfigParser
from pathlib import Path

from jira import JIRA


class JiraAccess():
    def __init__(self, configPath):
        config = ConfigParser()
        config.read(configPath)
        self.jira = JIRA(
            {'server': config.get('JIRA', 'JIRA_SERVER')},
            basic_auth=(
                config.get('JIRA', 'EMAIL_ADDRESS'),
                config.get('JIRA', 'JIRA_KEY')
            )
        )
        self.projectId = self.jira.project('TIGER').id
        self.emailAddress = config.get('JIRA', 'EMAIL_ADDRESS')

    def getAllSubtasks(self, issueKeys):
        issues = self.getIssues(issueKeys)
        allFilteredSubtasks = []
        for issue in issues:
            subtasks = [
                st.key
                for st
                in self._getSubtasksAsIssues(issue)
                if st.fields.assignee is not None
                and st.fields.assignee.emailAddress.lower() == self.emailAddress.lower()
            ]
            subtasks.reverse()
            allFilteredSubtasks.extend(subtasks)
        return allFilteredSubtasks

    def _getSubtasksAsIssues(self, parentIssue):
        # Grab the subtasks
        subtaskIds = [subtask.key for subtask in parentIssue.fields.subtasks]
        return self.getIssues(subtaskIds) if subtaskIds else []

    def getIssues(self, issueKeys=None):
        """
        Gets all issues in current sprint, plus any additional issues specified
        by issueKeys, which is a list of keys.
        """
        sprintQuery = f"project={self.projectId}"
        if issueKeys is not None and len(issueKeys) > 0:
            keyString = ', '.join([f'\"{key}\"' for key in issueKeys])
            keyQuery = f"key IN ({keyString})"
            queryString = f"({keyQuery}) OR ({sprintQuery})"
        else:
            queryString = sprintQuery
        return self.jira.search_issues(
            queryString,
            maxResults=False
        )
