import { useState } from "react";

export default function ClarifyFlow({ trigger, questions, onComplete }) {
    const [step, setStep] = useState(0);
    const [answers, setAnswers] = useState({});
    const q = questions[step];

    function choose(value) {
        const next = { ...answers, [q.key]: value };
        setAnswers(next);
        if (step + 1 < questions.length) {
            setStep(step + 1);
        } else {
            onComplete(next);
        }
    }

    return (
        <div className="mx-auto max-w-lg px-6 py-16 text-center">
            <p className="text-sm text-ink-faint">
                &ldquo;{trigger}&rdquo; could mean a few things — quick question:
            </p>
            <h2 className="mt-3 font-display text-2xl text-ink">{q.prompt}</h2>

            <div className="mt-6 flex flex-wrap justify-center gap-2">
                {q.options.map((opt) => (
                    <button
                        key={opt}
                        type="button"
                        onClick={() => choose(opt)}
                        className="rounded-full border border-line bg-surface px-4 py-2 text-sm text-ink-soft transition-colors hover:border-amber-400 hover:text-ink"
                    >
                        {opt}
                    </button>
                ))}
            </div>

            <p className="mt-6 text-xs text-ink-faint">
                Question {step + 1} of {questions.length}
            </p>
        </div>
    );
}