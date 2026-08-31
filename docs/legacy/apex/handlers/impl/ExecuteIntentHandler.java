package apex.handlers.impl;

import apex.core.ActionResult;
import apex.core.ApexContext;
import apex.handlers.AbstractHandler;

import java.util.HashMap;
import java.util.Map;

/**
 * Handler que executa outra intent registrada dinamicamente.
 */
public class ExecuteIntentHandler extends AbstractHandler {

    public ExecuteIntentHandler(ApexContext context) {
        super(context);
    }

    @Override
    public String getIntentName() {
        return "execute_intent";
    }

    @Override
    public String getDescription() {
        return "Executa uma intent registrada informada em tempo de execução.";
    }

    @Override
    public String[] getRequiredParams() {
        return new String[0];
    }

    @Override
    protected ActionResult performAction(Map<String, Object> params, ApexContext ctx) {

        String intentName = params.get("intent") instanceof String value ? value : null;

        if (intentName == null || intentName.isBlank()) {
            return ActionResult.fail("Nome da intent é obrigatório.", "Nome da intent é obrigatório.");
        }

        if ("execute_intent".equals(intentName) || "execute-intent".equals(intentName)) {
            return ActionResult.fail("Recursão não permitida para execute_intent.", "Recursão não permitida para execute_intent.");
        }

        Map<String, Object> intentParams = new HashMap<>();
        if (params.get("params") instanceof Map<?, ?> rawParams) {
            rawParams.forEach((key, value) -> {
                if (key != null) {
                    intentParams.put(String.valueOf(key), value);
                }
            });
        }

        var intentInfo = ctx.intentRegistry().find(intentName);

        if (intentInfo.isEmpty()) {
            return ActionResult.fail("Intent '" + intentName + "' não encontrada.", "Intent '" + intentName + "' não encontrada.");
        }

        try {
            return ctx.intentRegistry().execute(intentName, intentParams);

        } catch (Exception e) {
            return ActionResult.fail("Erro ao executar intent: " + e.getMessage(), e.getMessage());
        }
    }
}
