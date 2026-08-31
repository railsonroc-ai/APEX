package apex.feedback;

import apex.core.ActionResult;
import apex.core.ApexContext;
import apex.handlers.ApexHandler;

import java.util.Map;

/**
 * Regra individual de avaliação do ciclo de feedback.
 * Cada regra analisa o resultado da ação e retorna um Evaluation.
 */
public interface FeedbackRule {

    /**
     * Avalia o resultado de uma ação e retorna um objeto Evaluation.
     *
     * @param result  Resultado da ação (pode ser null em caso de erro antes da execução)
     * @param handler Handler que executou a ação
     * @param params  Parâmetros recebidos
     * @param context Contexto completo do APEX
     */
    Evaluation evaluate(ActionResult result,
                        ApexHandler handler,
                        Map<String, Object> params,
                        ApexContext context);
}