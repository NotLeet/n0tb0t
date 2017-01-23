import gspread
import pytz
from .Utils import _retry_gspread_func


@_retry_gspread_func
def _initialize_highlights_spreadsheet(self, spreadsheet_name):
    """
    Populate the highlights google sheet with its initial data.
    """
    gc = gspread.authorize(self.credentials)
    sheet = gc.open(spreadsheet_name)
    sheet.worksheets()  # Necessary to remind gspread that Sheet1 exists, otherwise gpsread forgets about it

    try:
        hls = sheet.worksheet('Highlight List')
    except gspread.exceptions.WorksheetNotFound:
        hls = sheet.add_worksheet('Highlight List', 1000, 4)
        sheet1 = sheet.worksheet('Sheet1')
        sheet.del_worksheet(sheet1)

    hls.update_acell('A1', 'User')
    hls.update_acell('B1', 'Stream Start Time EST')
    hls.update_acell('C1', 'Highlight Time')
    hls.update_acell('D1', 'User Note')


def highlight(self, message):
    """
    Logs the time in the video when something amusing happened.
    Takes an optional short sentence describing the event.
    Writes that data to a google spreadsheet.

    !highlight
    !highlight The caster screamed like a little girl!
    """
    user = self.ts.get_user(message)
    msg_list = self.ts.get_human_readable_message(message).split(' ')
    if len(msg_list) > 1:
        user_note = ' '.join(msg_list[1:])
    else:
        user_note = ''
    time_dict = self._get_live_time()
    if time_dict is not None:
        est_tz = pytz.timezone('US/Eastern')
        start_time_utc = time_dict['stream_start']
        start_time_est = est_tz.normalize(start_time_utc.replace(tzinfo=pytz.utc).astimezone(est_tz))
        time_str = 'Approximately {hours}, {minutes} and {seconds} into the stream.'.format(
                hours=time_dict['hour'], minutes=time_dict['minute'], seconds=time_dict['second'])

        spreadsheet_name, _ = self.spreadsheets['highlights']
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        ws = sheet.worksheet('Highlight List')
        records = ws.get_all_records()  # Doesn't include the first row
        next_row = len(records) + 2
        ws.update_cell(next_row, 1, user)
        ws.update_cell(next_row, 2, str(start_time_est)[:-6])
        ws.update_cell(next_row, 3, time_str)
        ws.update_cell(next_row, 4, user_note)
        self._add_to_whisper_queue(user, 'The highlight has been added to the spreadsheet for review.')
