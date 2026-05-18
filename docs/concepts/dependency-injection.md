# Dependency injection

**Dependency injection** is the practice of passing an object's
collaborators in **from the outside** instead of constructing
them inside the object itself. It is a code-shape concern -
not a framework, not a library. Tripack is one of many tools
that automate the wiring; the underlying idea exists with or
without one.

## The shape of the problem

A `LogShipper` needs a `Clock` (to timestamp events) and a
`Logger` (to write them). Without injection, the shipper
builds both:

```python
class LogShipper:
    def __init__(self) -> None:
        self.clock = Clock()
        self.logger = Logger()

    def ship(self, event: Event) -> None:
        self.logger.write(f"[{self.clock.now()}] {event}")
```

The shipper now hard-codes two collaborators. Any test that
exercises it will instantiate **real** `Clock` and `Logger`
objects, with whatever side effects they carry (system time,
file I/O, network). Any product variation - a test clock that
returns a fixed value, a logger that buffers to memory -
requires editing `LogShipper` itself.

## The fix

Make the collaborators **parameters** of the constructor:

```python
class LogShipper:
    def __init__(self, clock: Clock, logger: Logger) -> None:
        self.clock = clock
        self.logger = logger

    def ship(self, event: Event) -> None:
        self.logger.write(f"[{self.clock.now()}] {event}")
```

The shipper no longer knows where its dependencies come from.
A test passes `FixedClock()` and `MemoryLogger()`; production
passes `SystemClock()` and `FileLogger()`. The shipper's
behaviour does not change - only its **wiring** does.

## What injection buys

- **Testability**. Tests pass fakes / stubs / mocks without
  patching or monkey-business. The collaborators are part of
  the function signature, not hidden inside.
- **Swappability**. Producing a CLI build with a
  console-formatted logger and a web build with a structured
  logger is two different bindings, not two different
  shippers.
- **Single responsibility**. The shipper does shipping. It
  does not also do clock construction or logger configuration.
- **Lifecycle separation**. `Clock` lifetime is decided at the
  wiring layer (do you reuse one? do you make a new one per
  request?), not baked into the shipper.

## What injection does NOT do

- It does not eliminate coupling - the shipper still
  **depends** on `Clock` and `Logger`. It removes one form of
  coupling (constructing them) at the cost of explicitness
  (declaring them).
- It does not require a container. `LogShipper(Clock(),
  Logger())` is dependency injection by hand. A container
  automates this when the wiring grows beyond one or two
  hops.
- It does not solve the *transitive* problem. If `Clock`
  itself needs a `TimeZone`, the wiring at the top has to
  thread the `TimeZone` through. A container does this part
  too.

## Anti-patterns

**Service Locator**. Instead of receiving collaborators, the
shipper looks them up:

```python
class LogShipper:
    def ship(self, event: Event) -> None:
        clock = locator.get(Clock)
        logger = locator.get(Logger)
        logger.write(f"[{clock.now()}] {event}")
```

This **looks** like injection but is the opposite: the
dependencies are now hidden again, the call site cannot see
what the shipper actually needs, and tests have to configure
the locator instead of just passing fakes. The Tripack
container exposes `resolve` for boundary cases (composition
root, framework adapters); using it from inside a service
re-introduces the same opacity as the original construction.

## Where Tripack fits

When the manual wiring becomes tedious - a CLI with five
commands that each touch ten services that each need three
collaborators - a container takes over the work of looking
up registered factories and chaining them. The shipper still
declares its dependencies as constructor parameters; the
container reads those declarations and wires them up.

The next two pages explain the **principle** the container
embodies ([inversion of control](inversion-of-control.md))
and the **mechanism** that makes it usable
([the IoC container](ioc-container.md)).
