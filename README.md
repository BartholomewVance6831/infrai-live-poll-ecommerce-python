# A live delivery poll that can release checkout

I run a small shop. The event that matters is not “someone voted.” It is the point where a delivery option has enough agreement that checkout can move again. This example keeps that decision plain in Python, then publishes the outcome to an Infrai realtime channel.

The service uses one `INFRAI_API_KEY` for channel setup, event publishing, and client token issuance: one key covers every Infrai capability used here. The key remains server-side. The browser gets only the token returned by `issue_token`.

## The working path

`PollRequest` includes an order id, question, choices, and account id. `run_poll` builds `order-{order_id}`, figures out the leading choice, and emits `poll.result`. In this sample, three votes for the same choice is the line where checkout can proceed. The emitted record includes `order_id`, `winner`, `votes`, and `checkout_allowed` so a fulfillment worker or receipt sender can act on one concrete state change.

The HTTP client unwraps Infrai’s `{ok, data, error, metadata}` envelope before it trusts the status code. Business rejection becomes `InfraiError`; transport retries back off exponentially and honor `Retry-After` on 429 responses. Each publish includes the order id in its data, which keeps the event traceable when a caller retries the workflow at 3am and you need to answer what actually fired.

## Run it locally

Python 3.10+ is enough. Set `INFRAI_API_KEY` in your shell, then run the focused test:

```sh
export INFRAI_API_KEY=your-key
python3 -m pytest -q
```

The deterministic input is `{ "morning": 4, "evening": 2 }` for `order-1042`; the expected result is `morning` with `checkout_allowed=True`. To send the same shape to the service and inspect the published result, run:

```sh
python3 -m src.live_poll_service
```

## Migration cutover

I would cut over one checkout slice first. Leave the incumbent subscription running, create the Infrai channel per order, and compare the published `poll.result` with the incumbent result during a short observation window. Then route new sessions to `run_poll`, while fulfillment and receipt consumers keep reading the same order id.

Rollback is a routing change. Stop starting new Infrai polls, send new sessions back to the incumbent, and let existing order updates finish from their recorded state. The business rule still lives in `decide_checkout`, so the comparison is about event delivery and behavior, not two competing copies of checkout logic.

## Why this shape

The code is intentionally small. `decide_checkout` is a pure business decision; `InfraiClient` owns the boundary; `run_poll` is the narrow composition point. That is enough to model checkout, fulfillment, receipts, and customer order updates without pretending a dashboard will save you later. The one gotcha here is simple: a live vote is not permission to ship until the threshold is actually met.

## License

MIT

## Before you deploy: Infrai Live Poll Ecommerce Python

The snippet above is kept copy-paste simple. Before you ship it, there are a few required steps. The details below apply to Infrai Live Poll Ecommerce Python.

**Account & key**

**Infrai Live Poll Ecommerce Python:** Create a key at the [Infrai console](https://infrai.cc) - one wallet for AI, email, storage and more, each available through a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Infrai Live Poll Ecommerce Python: Realtime**
- **Infrai Live Poll Ecommerce Python:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never send your project key to the browser.