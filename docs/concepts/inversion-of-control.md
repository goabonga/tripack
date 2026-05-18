# Inversion of control

**Inversion of control** (IoC) is the principle behind the
Hollywood line: *don't call us, we'll call you*. Concretely:
the code you write does not invoke the framework; the
framework invokes your code at the moments it owns. The
*direction of calls* is reversed compared to a plain library.

[Dependency injection](dependency-injection.md) is one
application of this principle - the framework controls **who
constructs what** instead of the consumer. But IoC is broader.

## Library vs framework

Consider an event-dispatching loop. A **library** for this
might look like:

```python
import event_bus

bus = event_bus.EventBus()
while True:
    event = bus.next()
    if event.kind == "ping":
        respond("pong")
    elif event.kind == "shutdown":
        break
```

Your code drives the loop. The library hands you primitives.
You decide when to call `bus.next()`, what to do with each
event, how to terminate. The flow is yours.

A **framework** for the same thing might look like:

```python
import event_bus

@event_bus.on("ping")
def handle_ping(event: Event) -> None:
    respond("pong")


@event_bus.on("shutdown")
def handle_shutdown(event: Event) -> None:
    raise SystemExit


event_bus.run()
```

The framework runs the loop. Your code is a set of handlers
that it calls when events arrive. You never write the loop;
you describe the *reactions*. Control of the dispatch is the
framework's.

The framework has **inverted control**: instead of you driving
it, it drives you. The handlers, the structure of the
configuration, the lifecycle - all belong to the framework.

## Why invert at all

- **Boilerplate.** The loop is the same in every consumer; the
  reactions are different. Inverting means writing the
  loop *once* (in the framework) and the reactions *as needed*
  (in user code).
- **Composition.** When the framework owns the flow, multiple
  user components can hook in without coordinating. Each
  handler is independent; the framework merges them.
- **Lifecycle.** Setup, teardown, error handling - all
  cross-cutting concerns happen *around* user code in a
  consistent way the framework defines, so each handler does
  not re-implement them.

## Hollywood, applied to construction

For dependency wiring, the inversion is the same shape. In a
plain library, **you** construct your services and pass them
to each other:

```python
clock = SystemClock()
cache = MemoryCache(clock)
config = Config.load("/etc/app.toml")
app = App(clock, cache, config)
app.run()
```

You drive construction. You decide order. You hold all the
references.

With IoC for construction, you describe what should exist; a
container decides how to instantiate:

```python
container.bind(Clock, SystemClock)
container.bind(Cache, MemoryCache)        # auto-injects Clock
container.bind(Config, lambda: Config.load("/etc/app.toml"))
container.bind_class(App)                  # auto-injects the rest

app = container.resolve(App)
app.run()
```

The container handles the order, the caching, the lifecycle.
You handle the **declarations**. The control over *how* and
*when* dependencies materialise is inverted from your code to
the container.

## Where Tripack inverts control

| Concern | Without IoC | With Tripack |
| --- | --- | --- |
| Construction order | manual, top-down | container resolves on demand |
| Lifecycle (singleton, scoped, transient) | manual reuse / re-creation | declared per binding, enforced by the container |
| Scope boundaries | manual context-mgmt | `Container.scope()` / `Container.ascope()` |
| Teardown | manual `close()` calls | LIFO auto-close on scope / container exit |
| Cycle detection | discovered at runtime | guarded by the cycle detector at every resolve |
| Configuration | hand-coded `if/else` | declarative TOML / JSON / YAML |

In every row, the consumer **describes** intent; the framework
**executes** it. That is the IoC contract.

## Where IoC does NOT belong

- A 50-line script that wires three objects in one place does
  not need a container. The manual form is shorter, clearer,
  and has fewer abstractions.
- Code that needs precise control over timing, ordering, or
  resource acquisition (a hot loop, an interrupt handler, a
  GPU kernel launcher) is *also* a poor IoC candidate -
  losing control of *when* things happen is the whole point
  of IoC, which is the wrong trade for these cases.
- Test code occasionally benefits from explicit construction
  over container-driven wiring - one test, one explicit
  graph, no opaque "what got injected here?". The
  `Container` API supports both styles; pick whichever makes
  the test less surprising.

The next page describes the **mechanism** that turns the IoC
principle into a usable runtime: the
[IoC container](ioc-container.md) itself.
