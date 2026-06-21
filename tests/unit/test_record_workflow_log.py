from geoifcassets.application.dto.log_entry import LogEntry
from geoifcassets.application.use_cases.record_workflow_log import RecordWorkflowLogUseCase


class MemoryDeveloperLogger:
    def __init__(self):
        self.entries = []

    def log(self, entry):
        self.entries.append(entry)


class MemoryUserLogger:
    def __init__(self):
        self.entries = []

    def notify(self, entry):
        self.entries.append(entry)


def test_record_workflow_log_records_developer_log():
    developer_logger = MemoryDeveloperLogger()
    use_case = RecordWorkflowLogUseCase(developer_logger)
    entry = LogEntry(level="INFO", operation="plugin_load", message="Loaded")

    use_case.execute(entry)

    assert developer_logger.entries == [entry]


def test_record_workflow_log_can_record_user_log():
    developer_logger = MemoryDeveloperLogger()
    user_logger = MemoryUserLogger()
    use_case = RecordWorkflowLogUseCase(developer_logger, user_logger)
    entry = LogEntry(level="INFO", operation="open_panel", message="Panel opened")

    use_case.execute(entry, visible_to_user=True)

    assert developer_logger.entries == [entry]
    assert user_logger.entries == [entry]
