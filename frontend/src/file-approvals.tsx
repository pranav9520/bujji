export type FilePlan = {
  id: string;
  expires_in: number;
  actions: {
    kind: string;
    source?: string;
    destination?: string;
    text?: string;
    bytes?: number;
  }[];
};
export type ToolEvent = {
  step: number;
  tool: string;
  status: string;
  summary?: string;
  target?: string;
};
export function FileApprovals({
  plans,
  disabled,
  onDecision,
}: {
  plans: FilePlan[];
  disabled: boolean;
  onDecision: (id: string, confirmed: boolean) => void;
}) {
  return (
    <>
      {plans.map((plan) => (
        <div className="chat-file-approval" key={plan.id}>
          <h3>Approve these actions?</h3>
          <p>
            Nothing below has run yet. This approval expires ten minutes after
            preparation. Existing files will not be overwritten.
          </p>
          <ol>
            {plan.actions.map((action, index) => (
              <li key={index}>
                <strong>{action.kind.replaceAll("_", " ")}</strong>
                {action.source && <p>From: {action.source}</p>}
                {action.destination && <p>To: {action.destination}</p>}
                {typeof action.bytes === "number" && (
                  <small>{action.bytes.toLocaleString()} bytes</small>
                )}
                {action.text !== undefined && (
                  <details>
                    <summary>
                      {action.kind === "remember"
                        ? "Memory to save"
                        : "New file contents"}
                    </summary>
                    <pre>{action.text}</pre>
                  </details>
                )}
              </li>
            ))}
          </ol>
          <div className="document-actions">
            <button
              className="primary"
              disabled={disabled}
              onClick={() => onDecision(plan.id, true)}
            >
              Approve and run
            </button>
            <button
              disabled={disabled}
              onClick={() => onDecision(plan.id, false)}
            >
              Cancel these actions
            </button>
          </div>
        </div>
      ))}
    </>
  );
}
