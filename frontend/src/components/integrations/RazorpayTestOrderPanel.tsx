import { useState } from "react";
import { ClipboardCheck, Loader2, Search, ShoppingBag } from "lucide-react";
import { createRazorpayTestOrder, getRazorpayMapping } from "@/lib/api/razorpay";
import type { RazorpayMappingResponse, RazorpayTestOrderResponse } from "@/lib/types";
import { formatINR } from "@/lib/format";

function safeError() {
  return "The Razorpay Test Mode request could not be completed. Please check the backend and try again.";
}

export function RazorpayTestOrderPanel() {
  const [internalOrderId, setInternalOrderId] = useState("");
  const [amount, setAmount] = useState("10000");
  const [receipt, setReceipt] = useState("");
  const [created, setCreated] = useState<RazorpayTestOrderResponse | null>(null);
  const [mapping, setMapping] = useState<RazorpayMappingResponse | null>(null);
  const [loading, setLoading] = useState<"create" | "mapping" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const createOrder = async () => {
    const paise = Number(amount);
    if (!internalOrderId.trim() || !Number.isInteger(paise) || paise <= 0) {
      setError("Enter an internal order ID and a positive amount in paise.");
      return;
    }
    setLoading("create");
    setError(null);
    setMapping(null);
    try {
      const response = await createRazorpayTestOrder({
        amount: paise,
        currency: "INR",
        receipt: receipt.trim() || undefined,
        internal_order_id: internalOrderId.trim(),
      });
      if (!response.created) throw new Error("not-created");
      setCreated(response);
    } catch {
      setError(safeError());
    } finally {
      setLoading(null);
    }
  };

  const viewMapping = async () => {
    if (!internalOrderId.trim()) {
      setError("Enter an internal order ID to view its mapping.");
      return;
    }
    setLoading("mapping");
    setError(null);
    try {
      const response = await getRazorpayMapping(internalOrderId.trim());
      setMapping(response);
      if (!response.found) setError("No Razorpay Test Mode mapping was found for this order.");
    } catch {
      setError(safeError());
    } finally {
      setLoading(null);
    }
  };

  return (
    <section className="panel p-4">
      <div className="flex items-start gap-2.5">
        <span className="flex size-8 items-center justify-center rounded-md bg-primary-soft text-primary">
          <ShoppingBag size={16} />
        </span>
        <div>
          <h2 className="text-sm font-semibold">Test Mode order mapping</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Create and inspect an internal order link. No live payment is made.
          </p>
        </div>
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <label className="text-xs text-muted-foreground sm:col-span-2">
          Internal order ID
          <input
            value={internalOrderId}
            onChange={(e) => setInternalOrderId(e.target.value)}
            placeholder="ORD-0042-..."
            className="mt-1 w-full rounded-md border border-border-strong bg-canvas px-2.5 py-2 text-xs text-foreground outline-none focus:border-primary"
          />
        </label>
        <label className="text-xs text-muted-foreground">
          Amount (paise)
          <input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            inputMode="numeric"
            className="mt-1 w-full rounded-md border border-border-strong bg-canvas px-2.5 py-2 text-xs text-foreground outline-none focus:border-primary"
          />
        </label>
        <label className="text-xs text-muted-foreground">
          Receipt (optional)
          <input
            value={receipt}
            onChange={(e) => setReceipt(e.target.value)}
            maxLength={40}
            className="mt-1 w-full rounded-md border border-border-strong bg-canvas px-2.5 py-2 text-xs text-foreground outline-none focus:border-primary"
          />
        </label>
      </div>
      {error && (
        <p
          role="alert"
          className="mt-3 rounded-md border border-negative/25 bg-negative-soft px-3 py-2 text-xs text-negative"
        >
          {error}
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void createOrder()}
          disabled={loading !== null}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {loading === "create" && <Loader2 size={12} className="animate-spin" />} Create Test Order
        </button>
        <button
          type="button"
          onClick={() => void viewMapping()}
          disabled={loading !== null}
          className="inline-flex items-center gap-1.5 rounded-md border border-border-strong px-3 py-2 text-xs font-semibold transition-colors hover:bg-muted disabled:opacity-50"
        >
          {loading === "mapping" ? (
            <Loader2 size={12} className="animate-spin" />
          ) : (
            <Search size={12} />
          )}{" "}
          View mapping
        </button>
      </div>
      {created && (
        <div className="mt-4 rounded-md border border-positive/25 bg-positive-soft p-3 text-xs">
          <p className="flex items-center gap-1.5 font-semibold text-positive">
            <ClipboardCheck size={13} /> Test order created
          </p>
          <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-muted-foreground">
            <dt>Internal order</dt>
            <dd className="num text-right text-foreground">{created.internal_order_id}</dd>
            <dt>Razorpay order</dt>
            <dd className="num text-right text-foreground">{created.razorpay_order_id}</dd>
            <dt>Amount</dt>
            <dd className="num text-right text-foreground">
              {created.amount == null ? "—" : formatINR(created.amount / 100)}
            </dd>
            <dt>Status</dt>
            <dd className="text-right text-foreground">{created.status ?? "—"}</dd>
          </dl>
        </div>
      )}
      {mapping?.found && mapping.razorpay_order && (
        <div className="mt-3 rounded-md border border-border bg-canvas p-3 text-xs">
          <p className="font-semibold">Mapped Razorpay order</p>
          <p className="mt-1 num text-muted-foreground">
            {mapping.razorpay_order.id} · {mapping.razorpay_order.status}
          </p>
          <p className="mt-1 text-muted-foreground">
            {formatINR(mapping.razorpay_order.amount / 100)} · {mapping.razorpay_order.currency}
          </p>
        </div>
      )}
    </section>
  );
}
