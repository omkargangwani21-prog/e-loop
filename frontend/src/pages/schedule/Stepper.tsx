export function Stepper({ steps, current }: { steps: string[]; current: number }) {
  return (
    <ol className="stepper" aria-label="Progress">
      {steps.map((label, index) => {
        const state = index < current ? "is-done" : index === current ? "is-current" : "";
        return (
          <li key={label} className={`stepper__item ${state}`} aria-current={index === current ? "step" : undefined}>
            <span className="stepper__index" aria-hidden="true">
              {index + 1}
            </span>
            <span>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
