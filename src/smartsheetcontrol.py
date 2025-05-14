from smartsheet import Smartsheet
from smartsheet.models import (Cell, Column, Comment, Discussion, Report,
                               ReportRow, Row)


class Sheet:
    def __init__(self, sheet):
        self.sheet = sheet
        # The API identifies columns by Id, but it's more convenient to refer to column names
        self._column_map = {column.title: column.id for column in sheet.columns}
        # Keeps a running track of updates using row ID as keys and the row object as values
        # When running update_rows, use list(row_updates.values())
        self.row_updates = {}

    # Helper function to find cell in a row
    def get_cell_by_column_name(self, row, column_name) -> Cell:
        column_id = self._column_map[column_name]
        return row.get_column(column_id)
    
    def get_rows(self) -> list[Row]:
        return self.sheet.rows
    
    def get_columns(self) -> list[Column]:
        return self.sheet.columns



class Report(Sheet):
    def __init__(self, report: Report):
        self.discussions = report.discussions
        self.source_sheets = {src_sheet.id: Sheet(src_sheet) for src_sheet in report.source_sheets}
        super().__init__(report)

    # Helper function to find cell in a row
    def get_cell_by_column_name(self, row: ReportRow, column_name: str) -> Cell:
        sheet = self.source_sheets[row.sheet_id]
        return sheet.get_cell_by_column_name(row, column_name)




class SmartsheetController:
    def __init__(self, access_token: str = None):
        self.client = Smartsheet(access_token)
        self.client.errors_as_exceptions(True)

    def get_sheet(self, sheet_id) -> Sheet:
        return Sheet(self.client.Sheets.get_sheet(sheet_id))

    def get_report(self, report_id) -> Report:
        return Report(self.client.Reports.get_report(report_id, include=['sourceSheets']))

    def update_rows(self, sheet):
        if sheet.row_updates:
            return self.client.Sheets.update_rows(sheet.sheet.id, list(sheet.row_updates.values()))
        
    def update_row(self, sheet, row):
        self.client.Sheets.update_rows(sheet.sheet.id, [row])

    def update_report_rows(self, report: Report):
        for sheet in report.source_sheets.values():
            self.update_rows(sheet)

    def get_discussions(self, sheet_id):
        response = self.client.Discussions.get_all_discussions(sheet_id, include_all=True)
        return response.data
    
    def create_discussion_on_row(self, sheet_id, row_id, comment):
        discuss = Discussion({'comment': Comment({'text' : comment})})
        self.client.Discussions.create_discussion_on_row(sheet_id, row_id, discuss)

    def create_comment(self, sheet_id, discussion_id, comment):
        comm = Comment({'text': comment})
        self.client.Discussions.add_comment_to_discussion(sheet_id, discussion_id, comm)

    def get_row_by_id(self, sheet_id, row_id):
        row = self.client.Sheets.get_row(sheet_id, row_id)
        return row

    def add_rows(self, sheet_id, rows):
       result = self.client.Sheets.add_rows(sheet_id, rows)
       return result