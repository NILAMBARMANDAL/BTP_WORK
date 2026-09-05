/**
 * Renders a transcript as individually-selectable words, keyed by their
 * stable `index` (never by text) — required so repeated Bengali words and
 * duplicate strings are each selectable independently. Never collapse this
 * into a single string; ARCHITECTURE.md requires structured word data.
 *
 * `correctionsByIndex`: optional map of wordIndex -> correction status
 * ("open" | "accepted") so accepted corrections can render the corrected text.
 */
export function TranscriptView({ words, selectedIndex, onSelectWord, correctionsByIndex = {} }) {
  if (!words || words.length === 0) {
    return <p className="hint">No transcript yet.</p>;
  }

  return (
    <p className="transcript" lang="bn">
      {words.map((word) => {
        const correction = correctionsByIndex[word.index];
        const displayText = correction?.acceptedText ?? word.text;
        const isSelected = word.index === selectedIndex;
        const isAccepted = correction?.status === "accepted";

        const classNames = ["transcript-word"];
        if (isSelected) classNames.push("transcript-word--selected");
        if (isAccepted) classNames.push("transcript-word--corrected");

        return (
          <span
            key={word.index}
            className={classNames.join(" ")}
            onClick={() => onSelectWord(word.index)}
            title={
              word.confidence != null ? `confidence: ${(word.confidence * 100).toFixed(0)}%` : undefined
            }
          >
            {displayText}{" "}
          </span>
        );
      })}
    </p>
  );
}
