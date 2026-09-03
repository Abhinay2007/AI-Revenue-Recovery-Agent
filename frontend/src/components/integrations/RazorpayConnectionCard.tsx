import { useEffect, useState } from "react";
import { CheckCircle2, CircleAlert, Loader2, PlugZap } from "lucide-react";
import type { RazorpayConnectivity } from "@/lib/types";
import { getRazorpayConnectivity } from "@/lib/api/razorpay";

function connectionMessage(result: RazorpayConnectivity) {
  if (!result.configured) return "Test credentials are not configured on the backend.";
  if (!result.reachable) return "Razorpay Test Mode could not be reached.";
  if (!result.authentication_successful) return "Razorpay Test Mode authentication failed.";
  if (result.requested_test_resource_found === false)
    return "Authentication succeeded; the requested test order was not found.";
  return "Authentication successful";
}

export function RazorpayConnectionCard() {
  const [result, setResult] = useState<RazorpayConnectivity | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const check = async () => {
    setLoading(true);
    setError(null);
    try {
      setResult(await getRazorpayConnectivity());
    } catch {
      setResult(null);
      setError(
        "Unable to connect to the recovery service. Please check that the backend is running and try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void check();
  }, []);

  const connected = result?.reachable && result.authentication_successful;

  return (
    <section className="panel p-4" aria-label="Razorpay Test Mode connection">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex size-8 items-center justify-center rounded-md bg-primary-soft text-primary">
            <PlugZap size={16} />
          </span>
          <div>
            <h2 className="text-sm font-semibold">Razorpay</h2>
            <p className="label-xs mt-0.5">Test Mode</p>
          </div>
        </div>
        {connected ? (
          <CheckCircle2 size={17} className="text-positive" />
        ) : (
          <CircleAlert size={17} className="text-warning" />
        )}
      </div>
      <p className={`mt-4 text-sm font-semibold ${connected ? "text-positive" : "text-warning"}`}>
        {connected ? "Connected" : result ? "Disconnected" : "Not checked"}
      </p>
      <p className="mt-1 min-h-8 text-xs text-muted-foreground">
        {error ??
          (result
            ? connectionMessage(result)
            : "Check the backend connection to Razorpay Test Mode.")}
      </p>
      <div className="mt-3 flex items-center justify-between gap-3">
        <p className="text-[11px] text-subtle-foreground">
          {result
            ? `Last checked ${new Date().toLocaleTimeString("en-IN")}`
            : "Credentials stay server-side"}
        </p>
        <button
          type="button"
          onClick={() => void check()}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-md border border-border-strong px-2.5 py-1.5 text-xs font-semibold transition-colors hover:bg-muted disabled:opacity-50"
        >
          {loading && <Loader2 size={12} className="animate-spin" />}
          {loading ? "Checking..." : "Check connection"}
        </button>
      </div>
    </section>
  );
}
