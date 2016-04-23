import collections


class PlayerQueue:
    def __init__(self, cycle_num=7):
        self._queue = collections.deque()
        self.cycle_num = cycle_num

    def push(self, player, priority):
        index = None
        for i, tup in enumerate(self._queue):
            if player == tup[0]:
                raise RuntimeError('That player already exists in this queue')
            elif index is None and priority >= tup[1]:
                index = i

        if index is not None:
            self._queue.insert(index, (player, priority))
        else:
            self._queue.append((player, priority,))

    def pop(self):
        return self._queue.pop()[0]

    def pop_all(self):
        return_list = []
        players = min(self.cycle_num, len(self._queue))
        for player in range(players):
            return_list.append(self.pop())
        return return_list


