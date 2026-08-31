package apex.handlers.impl;

import apex.core.ActionResult;
import apex.core.ApexContext;
import apex.handlers.AbstractHandler;

import java.util.List;
import java.util.Map;

/**
 * Handler que lista as intents registradas no agente.
 */
public class ListIntentsHandler extends AbstractHandler {

    public ListIntentsHandler(ApexContext context) {
        super(context);
    }

    @Override
    public String getIntentName() {
        return "list_intents";
    }

    @Override
    public String getDescription() {
        return "Lista as intents registradas no agente.";
    }

    @Override
    public String[] getRequiredParams() {
        return new String[0];
    }

    @Override
    protected ActionResult performAction(Map<String, Object> params, ApexContext ctx) {

        List<Map<String, Object>> intents = ctx.intentRegistry().list().stream()
                .map(i -> Map.of(
                        "name", i.name(),
                        "description", i.description()
                ))
                .toList();

        return ActionResult.ok(
                intents.size() + " intents registradas.",
                Map.of("intents", intents),
                null
        );
    }
}
