package apex.feedback;

import java.io.Serial;
import java.io.Serializable;
import java.time.Instant;

/**
 * Registro individual de uma avaliação feita pelo ApexFeedbackLoop.
 * Representa um item do histórico de feedback.
 */
public class FeedbackRecord implements Serializable {

    @Serial
    private static final long serialVersionUID = 20260303L;

    private final Instant timestamp;
    private final String intent;
    private final boolean success;
    private final Evaluation.Severity severity;
    private final String message;

    public FeedbackRecord(Instant timestamp, String intent, boolean success, Evaluation.Severity severity, String message) {
        this.timestamp = timestamp;
        this.intent = intent;
        this.success = success;
        this.severity = severity;
        this.message = message;
    }

    public Instant timestamp() {
        return timestamp;
    }

    public String intent() {
        return intent;
    }

    public boolean success() {
        return success;
    }

    public Evaluation.Severity severity() {
        return severity;
    }

    public String message() {
        return message;
    }
}