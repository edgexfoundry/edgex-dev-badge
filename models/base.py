class Base:
    def __init__(self, **entries):
        self.__dict__.update(entries)

    def __repr__(self):
        return f"{self.__dict__}"
