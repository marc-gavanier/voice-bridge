def next_pass[T](shuffled: tuple[T, ...], *, last: T | None) -> tuple[T, ...]:
    first, rest = shuffled[:1], shuffled[1:]
    return (*rest, *first) if first == (last,) else shuffled
