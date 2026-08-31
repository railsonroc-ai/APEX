package apex.feedback;

import java.io.Serial;
import java.io.Serializable;

/**
 * Representa o resultado de uma avaliação feita pelo ApexFeedbackLoop.
 * Contém severidade e mensagem explicativa.
 */
public class Evaluation implements Serializable {

    @Serial
    private static final long serialVersionUID = 20260303L;

    private final Severity severity;
    private final String message;

    public Evaluation(Severity severity, String message) {
        this.severity = severity;
        this.message = message;
    }

    public Severity severity() {
        return severity;
    }

    public String message() {
        return message;
    }

    /**
     * Níveis de severidade usados pelo sistema de feedback.
     */
    public enum Severity {
        OK,
        WARNING,
        ERROR
    }
}