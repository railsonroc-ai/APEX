package apex.handlers;

import apex.core.ActionResult;
import apex.core.ApexContext;
import apex.core.ApexException;

import java.util.Map;
import java.util.Objects;

/**
 * Interface base para todos os handlers do APEX.
 * Define contrato mínimo e comportamento padrão.
 */
public interface ApexHandler {

    /**
     * Nome da intenção que este handler atende.
     */
    String getIntentName();

    /**
     * Descrição da ação executada pelo handler.
     */
    String getDescription();

    /**
     * Lista de parâmetros obrigatórios.
     */
    String[] getRequiredParams();

    /**
     * Validação padrão dos parâmetros obrigatórios.
     */
    default void validate(Map<String, Object> params) {
        Objects.requireNonNull(params, "params é obrigatório");
        for (String req : getRequiredParams()) {
            if (!params.containsKey(req) || params.get(req) == null) {
                throw new ApexException(
                        ApexException.Tipo.PARAMETRO_INVALIDO,
                        "APX-PARAM-001",
                        "apex.parametro.obrigatorio.ausente",
                        req
                );
            }
        }
    }

    /**
     * Método principal de execução.
     */
    ActionResult execute(Map<String, Object> params, ApexContext context);

    /**
     * Hook opcional antes da execução.
     */
    default void preExecute(Map<String, Object> params, ApexContext context) {}

    /**
     * Hook opcional após a execução.
     */
    default void postExecute(ActionResult result, ApexContext context) {}

    /**
     * Prioridade do handler (menor = executa primeiro).
     */
    default int getPriority() { return 100; }
}