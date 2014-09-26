import random
import sys
from time import sleep
from coroutine import coroutine
from functools import partial
from transducer import compose, mapping, filtering, identity, pairwise, batching, _UNSET
from transducer import Reduced


# Sinks

@coroutine
def rprint(sep='\n', end=''):
    """A coroutine sink which prints received items stdout

    Args:
        sep: Optional separator to be printed between received items.
        end: Optional terminator to be printed after the last item.
    """
    try:
        sys.stdout.write(str((yield)))
        while True:
            sys.stdout.write(sep)
            sys.stdout.write(str((yield)))
    except GeneratorExit:
        sys.stdout.write(end)
        raise StopIteration


class NullSink:
    """The /dev/null of coroutine sinks."""

    def send(self, item):
        pass

    def close(self, item):
        pass


# Sources

def iterable_source(iterable, target):
    """Convert an iterable into a stream of events."""
    for item in iterable:
        target.send(item)
    target.close()


def poisson_source(rate, event, target):
    """Send events at random times with uniform probability.

    Args:
        rate: The average number of events to send per second
        event: A function or type used to construct the item to send from a
            float duration.
        target: The target coroutine or sink.
    """
    while True:
        duration = random.expovariate(rate)
        sleep(duration)
        target.send(event(duration))


# Reducers

def sender(result, item):
    """A reducer for sending items to a coroutine.

    Args:
        result: A coroutine or sink.
        item: An item to send.
    """
    result.send(item)
    return result


# Transducible processes

@coroutine
def rreduce(reducer, target, initializer=_UNSET):
    """Reduce for coroutines.

    Args:
        reducer: The reducing object, which should support the initial(), step()
            and complete() methods.

        target: The coroutine or sink to which results will be sent.

        initializer: Optional initializer for reduction. If not provided, initial()
            will be called on the reducer to obtain the initial value.
    """
    accumulator = reducer.initial() if initializer is _UNSET else initializer
    try:
        while True:
            accumulator = reducer.step(accumulator, (yield))
            if isinstance(accumulator, Reduced):
                accumulator = accumulator.value
                break
    except GeneratorExit:
        pass

    target.send(reducer.complete(accumulator))
    target.close()
    raise StopIteration


def transduce(transducer, reducer, source, sink):
    source(rreduce(transducer(reducer), target=sink, initializer=sink))


# Functions to exercise the above

def main():
    transduce(transducer=compose(
                  mapping(lambda x: x > 0.5),
                  pairwise(),
                  filtering(lambda x: x[0]),
                  mapping(lambda x: x[1]),
                  batching(3)),
              reducer=sender,
              source=partial(poisson_source, 2.0, identity),
              sink=rprint())

if __name__ == '__main__':
    main()

