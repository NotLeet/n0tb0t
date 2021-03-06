import concurrent.futures

import gspread
import sqlalchemy

import config
import src.models as models
import src.utils as utils


class DeathGuessingMixin:
    def __init__(self):
        self.starting_spreadsheets_list.append('player_guesses')

    @utils.retry_gspread_func
    def _initialize_player_guesses_spreadsheet(self, spreadsheet_name):
        """
        Populate the player_guesses google sheet with its initial data.
        """
        gc = gspread.authorize(self.credentials)
        sheet = gc.open(spreadsheet_name)
        sheet.worksheets()  # Necessary to remind gspread that Sheet1 exists, otherwise gpsread forgets about it

        try:
            pgs = sheet.worksheet('Player Guesses')
        except gspread.exceptions.WorksheetNotFound:
            pgs = sheet.add_worksheet('Player Guesses', 1000, 3)
            sheet1 = sheet.get_worksheet(0)
            sheet.del_worksheet(sheet1)

        pgs.update_acell('A1', 'User')
        pgs.update_acell('B1', 'Current Guess')
        pgs.update_acell('C1', 'Total Guess')

    @utils.mod_only
    def start_guessing(self, db_session):
        """
        Allows users to guess about the number of deaths
        before the next progression checkpoint.
        Expresses this in chat.

        !start_guessing
        """
        mv_obj = db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'guessing-enabled').one()
        mv_obj.mv_value = "True"
        utils.add_to_public_chat_queue(self, "Guessing is now enabled.")

    @utils.mod_only
    def stop_guessing(self, db_session):
        """
        Stops users from guess about the number of deaths
        before the next progression checkpoint.
        Expresses this in chat.

        !stop_guessing
        """
        mv_obj = db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'guessing-enabled').one()
        mv_obj.mv_value = "False"
        utils.add_to_public_chat_queue(self, "Guessing is now disabled.")

    def guess(self, message, db_session):
        """
        Updates the database with a user's guess
        or informs the user that their guess
        doesn't fit the acceptable parameters
        or that guessing is disabled for everyone.

        !guess 50
        """
        user = self.service.get_message_display_name(message)
        if db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'guessing-enabled').one().mv_value == 'True':
            msg_list = self.service.get_message_content(message).split(' ')
            if len(msg_list) > 1:
                guess = msg_list[1]
                if guess.isdigit() and int(guess) >= 0:
                    self._set_current_guess(user, guess, db_session)
                    utils.add_to_appropriate_chat_queue(self, message, f"{user} your guess has been recorded.")
                else:
                    utils.add_to_appropriate_chat_queue(self, message, f"Sorry {user}, that's not a non-negative integer.")
            else:
                utils.add_to_appropriate_chat_queue(self, message, f"Sorry {user}, !guess must be followed by a non-negative integer.")
        else:
            utils.add_to_appropriate_chat_queue(self, message, f"Sorry {user}, guessing is disabled.")

    @utils.mod_only
    def start_guesstotal(self, db_session):
        """
        Enables guessing for the total number of deaths for the run.
        Modifies the value associated with the guess-total-enabled key
        in the miscellaneous values dictionary and writes it to the json file.

        !start_guesstotal
        """
        mv_obj = db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'guess-total-enabled').one()
        mv_obj.mv_value = "True"
        utils.add_to_public_chat_queue(self, "Guessing for the total amount of deaths is now enabled.")

    @utils.mod_only
    def stop_guesstotal(self, db_session):
        """
        Disables guessing for the total number of deaths for the run.

        !stop_guesstotal
        """
        mv_obj = db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'guess-total-enabled').one()
        mv_obj.mv_value = "False"
        utils.add_to_public_chat_queue(self, "Guessing for the total amount of deaths is now disabled.")

    def guesstotal(self, message, db_session):
        """
        Updates the database with a user's guess
        for the total number of deaths in the run
        or informs the user that their guess
        doesn't fit the acceptable parameters
        or that guessing is disabled for everyone.

        !guesstotal 50
        """
        user = self.service.get_message_display_name(message)
        if db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'guess-total-enabled').one().mv_value == "True":
            msg_list = self.service.get_message_content(message).split(' ')
            if len(msg_list) > 1:
                guess = msg_list[1]
                if guess.isdigit() and int(guess) >= 0:
                    self._set_total_guess(user, guess, db_session)
                    utils.add_to_appropriate_chat_queue(self, message, f"{user} your guess has been recorded.")
                else:
                    utils.add_to_appropriate_chat_queue(self, message, f"Sorry {user}, that's not a non-negative integer.")
            else:
                utils.add_to_appropriate_chat_queue(self, message, f"Sorry {user}, you need to include a number after your guess.")
        else:
            utils.add_to_appropriate_chat_queue(self, message, f"Sorry {user}, guessing for the total number of deaths is disabled.")

    @utils.mod_only
    def reset_guesses(self, db_session):
        """
        Clear all guesses so that users
        can guess again for the next segment
        of the run.

        !reset_guesses
        """
        db_session.execute(sqlalchemy.update(models.User.__table__, values={models.User.__table__.c.current_guess: None}))
        utils.add_to_public_chat_queue(self, "Guesses have been cleared.")

    @utils.mod_only
    def reset_total_guesses(self, db_session):
        """
        Clear all total guesses so that users
        can guess again for the next game
        where they guess about the total number of deaths

        !reset_total_guesses
        """
        db_session.execute(sqlalchemy.update(models.User.__table__, values={models.User.__table__.c.total_guess: None}))
        utils.add_to_public_chat_queue(self, "Guesses for the total number of deaths have been cleared.")

    @utils.retry_gspread_func
    def update_player_guesses_spreadsheet(self):
        """
        Updates the player guesses spreadsheet from the database.
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            db_session = self.Session()
            spreadsheet_name, web_view_link = self.spreadsheets['player_guesses']
            gc = gspread.authorize(self.credentials)
            sheet = gc.open(spreadsheet_name)
            ws = sheet.worksheet('Player Guesses')

            worksheet_width = 3

            all_users = db_session.query(models.User).all()
            users = [user for user in all_users if user.current_guess is not None or user.total_guess is not None]

            cells = ws.range(f'A2:C{len(users)+11}')
            for cell in cells:
                cell.value = ''
            ws.update_cells(cells)

            cells = ws.range(f'A2:C{len(users)+1}')
            for index, user in enumerate(users):
                name_cell_index = index * worksheet_width
                current_guess_cell_index = name_cell_index + 1
                total_guess_cell_index = current_guess_cell_index + 1

                cells[name_cell_index].value = user.name
                cells[current_guess_cell_index].value = user.current_guess
                cells[total_guess_cell_index].value = user.total_guess

            ws.update_cells(cells)
        return web_view_link

    @utils.mod_only
    def show_guesses(self):
        """
        Clears all guesses out of the google
        spreadsheet, then repopulate it from
        the database.

        !show_guesses
        """
        utils.add_to_command_queue(self, '_update_guess_spreadsheet')

    def _update_guess_spreadsheet(self):
        """
        Do all the actual work of updating the guess spreadsheet so that we can stick it in a function queue
        """
        web_view_link = self.spreadsheets['player_guesses'][1]
        short_url = self.shortener.short(web_view_link)
        self.update_player_guesses_spreadsheet()
        utils.add_to_public_chat_queue(self, f"Spreadsheet updated. {short_url}")

    @utils.mod_only
    def set_deaths(self, message, db_session):
        """
        Sets the number of deaths for the current
        leg of the run. Needs a non-negative integer.

        !set_deaths 5
        """
        user = self.service.get_message_display_name(message)
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) > 1:
            deaths_num = msg_list[1]
            if deaths_num.isdigit() and int(deaths_num) >= 0:
                self._set_deaths(deaths_num, db_session)
                utils.add_to_appropriate_chat_queue(self, message, f'Current deaths: {deaths_num}')
            else:
                utils.add_to_appropriate_chat_queue(self, message, f'Sorry {user}, !set_deaths should be followed by a non-negative integer')
        else:
            utils.add_to_appropriate_chat_queue(self, message, f'Sorry {user}, !set_deaths should be followed by a non-negative integer')

    @utils.mod_only
    def set_total_deaths(self, message, db_session):
        """
        Sets the total number of deaths for the run.
        Needs a non-negative integer.

        !set_total_deaths 5
        """
        user = self.service.get_message_display_name(message)
        msg_list = self.service.get_message_content(message).split(' ')
        if len(msg_list) > 1:
            total_deaths_num = msg_list[1]
            if total_deaths_num.isdigit() and int(total_deaths_num) >= 0:
                self._set_total_deaths(total_deaths_num, db_session)
                utils.add_to_appropriate_chat_queue(self, message, f'Total deaths: {total_deaths_num}')
            else:
                utils.add_to_appropriate_chat_queue(self, message, f'Sorry {user}, !set_total_deaths should be followed by a non-negative integer')
        else:
            utils.add_to_appropriate_chat_queue(self, message, f'Sorry {user}, !set_total_deaths should be followed by a non-negative integer')

    @utils.mod_only
    def adddeath(self, message, db_session):
        """
        Adds one to both the current sequence
        and total death counters.

        !adddeath
        """
        current_deaths, total_deaths = self._add_death(db_session)
        whisper_msg = f'Current Deaths: {current_deaths}, Total Deaths: {total_deaths}'
        utils.add_to_appropriate_chat_queue(self, message, whisper_msg)

    @utils.mod_only
    def removedeath(self, message, db_session):
        """
        Removes one from both the current sequence
        and total death counters.

        !removedeath
        """
        current_deaths, total_deaths = self._remove_death(db_session)
        whisper_msg = f'Current Deaths: {current_deaths}, Total Deaths: {total_deaths}'
        utils.add_to_appropriate_chat_queue(self, message, whisper_msg)

    @utils.mod_only
    def reset_deaths(self, db_session):
        """
        Sets the number of deaths for the current
        stage of the run to 0. Used after progressing
        to the next stage of the run.

        !reset_deaths
        """
        self._set_deaths('0', db_session)
        self.deaths(db_session)

    def deaths(self, db_session):
        """
        Sends the current and total death
        counters to the chat.

        !deaths
        """
        deaths = self._get_current_deaths(db_session)
        total_deaths = self._get_total_deaths(db_session)
        utils.add_to_public_chat_queue(self, f"Current Boss Deaths: {deaths}, Total Deaths: {total_deaths}")

    @utils.mod_only
    def winner(self, message, db_session):
        """
        Sends the name of the currently winning
        player to the chat. Should be used after
        stage completion to display who won.

        !winner
        """
        winners_list = []
        deaths = self._get_current_deaths(db_session)
        last_winning_guess = -1
        # If your guess was over the number of deaths you lose due to the price is right rules.
        users = db_session.query(models.User).filter(models.User.current_guess <= deaths).all()
        for user in users:
            if user.current_guess > last_winning_guess:
                winners_list = [user.name]
                last_winning_guess = user.current_guess
            elif user.current_guess == last_winning_guess:
                winners_list.append(user.name)
        if len(winners_list) == 1:
            winners_str = f"The winner is {winners_list[0]}."
        elif len(winners_list) > 1:
            winners_str = f'The winners are {", ".join(winners_list[:-1])} and {winners_list[-1]}!'
        else:
            caster = self.info['channel']
            winners_str = f'You all guessed too high. You should have had more faith in {caster}. {caster} wins!'
        utils.add_to_appropriate_chat_queue(self, message, winners_str)

    @utils.mod_only
    def total_winner(self, message, db_session):
        """
        Sends the name of the currently winning
        player for the total guesses to the chat.
        Should be used after game completion to display who won.

        !total_winner
        """
        winners_list = []
        total_deaths = self._get_total_deaths(db_session)
        last_winning_guess = -1
        # If your guess was over the number of deaths you lose due to the price is right rules.

        users = db_session.query(models.User).filter(models.User.total_guess <= total_deaths).all()
        for user in users:
            if user.total_guess > last_winning_guess:
                winners_list = [user.name]
                last_winning_guess = user.total_guess
            elif user.total_guess == last_winning_guess:
                winners_list.append(user.name)
        if len(winners_list) == 1:
            winners_str = f"The winner is {winners_list[0]}!"
        elif len(winners_list) > 1:
            winners_str = f'The winners are {", ".join(winners_list[:-1])} and {winners_list[-1]}!'
        else:
            caster = self.info['channel']
            winners_str = f'You all guessed too high. You should have had more faith in {caster}. {caster} wins!'
        utils.add_to_appropriate_chat_queue(self, message, winners_str)

    def _set_current_guess(self, user, guess, db_session):
        """
        Takes a user and a guess.
        Adds the user (if they don't already exist)
        and their guess to the users table.
        """
        db_user = db_session.query(models.User).filter(models.User.name == user).first()
        if not db_user:
            db_user = models.User(name=user)
            db_session.add(db_user)
        db_user.current_guess = guess

    def _set_total_guess(self, user, guess, db_session):
        """
        Takes a user and a guess
        for the total number of deaths.
        Adds the user and their guess
        to the users table.
        """
        db_user = db_session.query(models.User).filter(models.User.name == user).first()
        if not db_user:
            db_user = models.User(name=user)
            db_session.add(db_user)
        db_user.total_guess = guess

    def _get_current_deaths(self, db_session):
        """
        Returns the current number of deaths
        for the current leg of the run.
        """
        deaths_obj = db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'current-deaths').one()
        return deaths_obj.mv_value

    def _get_total_deaths(self, db_session):
        """
        Returns the total deaths that
        have occurred in the run so far.
        """
        total_deaths_obj = db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'total-deaths').one()
        return total_deaths_obj.mv_value

    def _add_death(self, db_session):
        """
        Adds a death to the current and total deaths
        """
        deaths = int(self._get_current_deaths(db_session))
        total_deaths = int(self._get_total_deaths(db_session))
        deaths += 1
        total_deaths += 1
        self._set_deaths(str(deaths), db_session)
        self._set_total_deaths(str(total_deaths), db_session)
        return deaths, total_deaths

    def _remove_death(self, db_session):
        """
        Removes a death from the current and total deaths.
        """
        deaths = int(self._get_current_deaths(db_session))
        total_deaths = int(self._get_total_deaths(db_session))
        deaths -= 1
        total_deaths -= 1
        self._set_deaths(str(deaths), db_session)
        self._set_total_deaths(str(total_deaths), db_session)
        return deaths, total_deaths

    def _set_deaths(self, deaths_num, db_session):
        """
        Takes a string for the number of deaths.
        Updates the miscellaneous values table and the txt file specified in the config.
        """
        if config.death_file_path != '':
            with open(config.death_file_path, 'w') as f:
                f.write(f'{deaths_num}')
        deaths_obj = db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'current-deaths').one()
        deaths_obj.mv_value = deaths_num

    def _set_total_deaths(self, total_deaths_num, db_session):
        """
        Takes a string for the total number of deaths.
        Updates the miscellaneous values table and the txt file specified in the config.
        """
        if config.total_death_file_path != '':
            with open(config.total_death_file_path, 'w') as f:
                f.write(f'{total_deaths_num}')
        total_deaths_obj = db_session.query(models.MiscValue).filter(models.MiscValue.mv_key == 'total-deaths').one()
        total_deaths_obj.mv_value = total_deaths_num
