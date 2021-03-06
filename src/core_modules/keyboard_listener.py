from pynput.keyboard import Key, Listener, KeyCode

import src.utils as utils


class KeyboardListenerMixin:
    def __init__(self):
        self.keyboard_listener = None

    def _on_press(self, key):
        # print('{0} pressed'.format(key))
        # print(key, type(key))
        # print(isinstance(key, KeyCode))
        pass

    def _on_release(self, key):
        # print('{0} released'.format(key))
        if isinstance(key, KeyCode):
            if key.char == '+':
                db_session = self.Session()
                self._add_death(db_session)
                db_session.commit()
                db_session.close()
            elif key.char == '-':
                db_session = self.Session()
                self._remove_death(db_session)
                db_session.commit()
                db_session.close()
        # else:
        #     if key == Key.esc:
        #         # Stop listener
        #         return False

    @utils.mod_only
    def start_keylogger(self):
        """
        Starts the bot listening for + and - to increment and decrement the death

        !start_keylogger
        """
        if self.keyboard_listener is not None:
            self.keyboard_listener.stop()
        self.keyboard_listener = Listener(on_press=self._on_press, on_release=self._on_release)
        self.keyboard_listener.start()
        utils.add_to_public_chat_queue(self, 'Now listening for keyboard input')

    @utils.mod_only
    def stop_keylogger(self):
        """
        Stops the bot listening from listening to keyboard input

        !stop_keylogger
        """
        self.keyboard_listener.stop()
        utils.add_to_public_chat_queue(self, 'No longer listening for keyboard input')
