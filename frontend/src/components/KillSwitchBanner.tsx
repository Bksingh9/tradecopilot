import { useDashboard, useTriggerKillSwitch } from "@/api/queries";
import { Button } from "./Button";

export function KillSwitchBanner() {
  const { data } = useDashboard();
  const trigger = useTriggerKillSwitch();

  if (!data) return null;

  if (data.kill_switch_active) {
    return (
      <div className="bg-bad/15 border border-bad/40 text-bad rounded-lg px-4 py-3 flex items-center justify-between">
        <div>
          <div className="font-semibold">Kill switch ACTIVE — new orders are blocked</div>
          <div className="text-xs opacity-80 mt-0.5">{data.kill_switch_reason || "no reason"}</div>
        </div>
        <span className="text-xs opacity-70">Clear it from Settings → Kill switch</span>
      </div>
    );
  }
  return (
    <div className="flex items-center justify-end">
      <Button
        variant="danger"
        loading={trigger.isPending}
        onClick={() => {
          if (confirm("Trigger your kill switch? This will block any new orders until you clear it.")) {
            trigger.mutate("user-initiated from dashboard");
          }
        }}
      >
        Trigger kill switch
      </Button>
    </div>
  );
}
