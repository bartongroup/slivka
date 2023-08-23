from collections.abc import Iterable


class _UnorderedListComparator(list):
    def __eq__(self, other: Iterable) -> bool:
        remaining_left = list(self)
        remaining_right = []
        for element in other:
            try:
                remaining_left.remove(element)
            except ValueError:
                remaining_right.append(element)
        return not remaining_left and not remaining_right


def in_any_order(*items):
    return _UnorderedListComparator(items)
