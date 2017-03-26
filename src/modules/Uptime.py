class UptimeMixin:

    def uptime(self):
        """
        Sends a message to stream saying how long the caster has been streaming for.

        !uptime
        """
        time_dict = self._get_live_time()
        if time_dict is not None:
            uptime_str = 'The channel has been live for {hours}, {minutes} and {seconds}.'.format(
                    hours=time_dict['hour'], minutes=time_dict['minute'], seconds=time_dict['second'])
            self._add_to_chat_queue(uptime_str)