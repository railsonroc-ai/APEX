package apex.handlers;

import apex.core.ActionResult;
import apex.core.ApexContext;
import apex.core.ApexException;

import java.util.Map;
import java.util.Objects;

/**
 * Classe base para todos os handlers do APEX.
 * Fornece validação de parâmetros, integração com sessão e padronização de execução.
 */
public abstract class AbstractHandler {

    protected final ApexContext context;

    public AbstractHandler(ApexContext context) {
        this.context = Objects.requireNonNull(context, "context não pode ser nulo");
    }

    /**
     * Nome do intent que este handler atende.
     */
    public abstract String getIntentName();

    /**
     * Descrição do handler.
     */
    public abstract String getDescription();

    /**
     * Parâmetros obrigatórios para execução.
     */
    public abstract String[] getRequiredParams();

    /**
     * Lógica principal do handler.
     */
    protected abstract ActionResult performAction(Map<String, Object> params, ApexContext ctx);

    /**
     * Execução padronizada com validação e integração com sessão.
     */
    public final ActionResult execute(Map<String, Object> params) {

        if (params == null) {
            throw new ApexException(
                    ApexException.Tipo.PARAMETRO_INVALIDO,
                    "APX-HND-NULLPARAM",
                    "apex.handler.parametro.nulo",
                    "Parâmetros não podem ser nulos."
            );
        }

        // Validação de parâmetros obrigatórios
        for (String required : getRequiredParams()) {
            if (!params.containsKey(required)) {
                throw new ApexException(
                        ApexException.Tipo.PARAMETRO_INVALIDO,
                        "APX-HND-MISSING",
                        "apex.handler.parametro.faltando",
                        "Parâmetro obrigatório ausente: " + required
                );
            }
        }

        try {
            return performAction(params, context);

        } catch (Exception e) {
            throw new ApexException(
                    ApexException.Tipo.EXECUCAO_FALHOU,
                    "APX-HND-FAIL",
                    "apex.handler.execucao.falhou",
                    e.getMessage()
            );
        }
    }
}