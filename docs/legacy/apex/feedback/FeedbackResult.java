package apex.feedback;

import java.io.Serial;
import java.io.Serializable;
import java.util.List;

/**
 * Resultado completo de uma avaliação feita pelo ApexFeedbackLoop.
 * Contém severidade, mensagem e histórico acumulado.
 */
public class FeedbackResult implements Serializable {

    @Serial
    private static final long serialVersionUID = 20260303L;

    private final Evaluation.Severity severity;
    private final String message;
    private final List<FeedbackRecord> history;

    public FeedbackResult(Evaluation.Severity severity, String message, List<FeedbackRecord> history) {
        this.severity = severity;
        this.message = message;
        this.history = history == null ? List.of() : List.copyOf(history);
    }

    public Evaluation.Severity severity() {
        return severity;
    }

    public String message() {
        return message;
    }

    public List<FeedbackRecord> history() {
        return history;
    }
}