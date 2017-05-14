import gspread
import pytz

import src.utils as utils
from config import time_zone_choice


class HighlightMixin:
    def highlight(self, message):
        """
        Logs the time in the video when something amusing happened.
        Takes an optional short sentence describing the event.
        Writes that data to a google spreadsheet.

        !highlight
        !highlight The caster screamed like a little girl!
        """
        user = self.service.get_message_display_name(message)
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) > 1:
            user_note = ' '.join(msg_list[1:])
        else:
            user_note = ''
        try:
            time_dict = utils.get_live_time()
        except RuntimeError as e:
            time_dict = None
            self._add_to_chat_queue(str(e))

        if time_dict is not None:
            user_tz = pytz.timezone(time_zone_choice)
            start_time_utc = time_dict['stream_start']
            start_time_est = user_tz.normalize(start_time_utc.replace(tzinfo=pytz.utc).astimezone(user_tz))
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