package apex.feedback;

import apex.core.ApexContext;
import apex.core.ApexException;

import java.io.Serial;
import java.io.Serializable;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Loop de feedback do APEX.
 * Avalia resultados, registra histórico e sugere melhorias.
 * Agora com null-safety completo e Serializable.
 */
public class ApexFeedbackLoop implements Serializable {

    @Serial
    private static final long serialVersionUID = 20260303L;

    private final ApexContext context;

    /**
     * Histórico de avaliações realizadas.
     */
    private final List<FeedbackRecord> history = new ArrayList<>();

    public ApexFeedbackLoop(ApexContext context) {
        this.context = context;
    }

    /**
     * Avalia o resultado de uma ação executada por um handler.
     */
    public FeedbackResult evaluate(String intent, boolean success, Map<String, Object> result) {

        // Null-safety total
        if (intent == null) intent = "unknown-intent";
        if (result == null) result = Map.of();

        Evaluation evaluation = evaluateInternal(intent, success, result);

        FeedbackRecord record = new FeedbackRecord(
                Instant.now(),
                intent,
                success,
                evaluation.severity(),
                evaluation.message()
        );

        history.add(record);

        return new FeedbackResult(
                evaluation.severity(),
                evaluation.message(),
                List.copyOf(history)
        );
    }

    private Evaluation evaluateInternal(String intent, boolean success, Map<String, Object> result) {

        if (!success) {
            return new Evaluation(
                    Evaluation.Severity.ERROR,
                    "A ação '" + intent + "' falhou. Verifique logs e rollback."
            );
        }

        if (result.isEmpty()) {
            return new Evaluation(
                    Evaluation.Severity.WARNING,
                    "A ação '" + intent + "' executou, mas não retornou dados."
            );
        }

        return new Evaluation(
                Evaluation.Severity.OK,
                "Ação '" + intent + "' executada com sucesso."
        );
    }

    /**
     * Retorna o histórico completo de feedback.
     */
    public List<FeedbackRecord> getHistory() {
        return List.copyOf(history);
    }
}