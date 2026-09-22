from endstone import Actor


class Mob(Actor):
    pass


class Item(Actor):
    def __init__(self, name="item"):
        super().__init__(name)
        self.item_stack = None
