package apex.core;

import apex.bootstrap.IntentBootstrap;
import apex.feedback.ApexFeedbackLoop;
import apex.feedback.Evaluation;
import apex.handlers.AbstractHandler;
import apex.handlers.impl.CreateModuleHandler;
import apex.handlers.impl.DeleteModuleHandler;
import apex.handlers.impl.EditModuleHandler;
import apex.handlers.impl.ExecuteIntentHandler;
import apex.handlers.impl.ListIntentsHandler;
import apex.handlers.impl.ListModulesHandler;
import apex.handlers.impl.TeachConceptHandler;

import java.io.Serial;
import java.io.Serializable;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Agente principal do APEX.
 * Responsável por registrar handlers, executar intents e integrar com feedback e rollback.
 */
public class ApexAgent implements Serializable {

    @Serial
    private static final long serialVersionUID = 20260303L;

    private final ApexContext context;

    /**
     * Registro de handlers por intent.
     */
    private final Map<String, AbstractHandler> handlers = new ConcurrentHashMap<>();

    public ApexAgent(ApexContext context) {
        this.context = context;
        IntentBootstrap.registerAll(context);
        registerDefaultHandlers();
    }

    /**
     * Registra um handler no agente.
     */
    public void registerHandler(AbstractHandler handler) {
        Objects.requireNonNull(handler, "handler não pode ser nulo");
        handlers.put(handler.getIntentName(), handler);
        context.intentRegistry().register(handler);
    }

    private void registerAlias(String alias, AbstractHandler handler) {
        handlers.put(alias, handler);
        context.intentRegistry().registerAlias(alias, handler);
    }

    /**
     * Registra handlers padrão automaticamente.
     * Evita risco de handlers esquecidos.
     */
    private void registerDefaultHandlers() {
        registerHandler(new TeachConceptHandler(context));

        CreateModuleHandler createModuleHandler = new CreateModuleHandler(context);
        registerHandler(createModuleHandler);

        // Compatibilidade com formato legado de intent
        registerAlias("create-module", createModuleHandler);

        ListModulesHandler listModulesHandler = new ListModulesHandler(context);
        registerHandler(listModulesHandler);

        // Compatibilidade com formato legado de intent
        registerAlias("list-modules", listModulesHandler);

        DeleteModuleHandler deleteModuleHandler = new DeleteModuleHandler(context);
        registerHandler(deleteModuleHandler);

        // Compatibilidade com formato legado de intent
        registerAlias("delete-module", deleteModuleHandler);

        EditModuleHandler editModuleHandler = new EditModuleHandler(context);
        registerHandler(editModuleHandler);

        // Compatibilidade com formato legado de intent
        registerAlias("edit-module", editModuleHandler);

        ListIntentsHandler listIntentsHandler = new ListIntentsHandler(context);
        registerHandler(listIntentsHandler);

        // Compatibilidade com formato legado de intent
        registerAlias("list-intents", listIntentsHandler);

        ExecuteIntentHandler executeIntentHandler = new ExecuteIntentHandler(context);
        registerHandler(executeIntentHandler);

        // Compatibilidade com formato legado de intent
        registerAlias("execute-intent", executeIntentHandler);
    }

    /**
     * Executa uma ação com base no intent informado.
     */
    public ActionResult execute(String intent, Map<String, Object> params) {

        Objects.requireNonNull(intent, "intent não pode ser nulo");
        if (params == null) params = Map.of();

        AbstractHandler handler = handlers.get(intent);

        if (handler == null) {
            throw new ApexException(
                    ApexException.Tipo.HANDLER_NAO_ENCONTRADO,
                    "APX-HND-404",
                    "apex.handler.nao.encontrado",
                    intent
            );
        }

        String snapshotId = null;

        try {
            if (context.isRollbackEnabled()) {
                snapshotId = context.rollback().createSnapshot(context.projectRoot());
            }

            ActionResult result = handler.execute(params);

            ApexFeedbackLoop feedback = context.feedbackLoop();
            feedback.evaluate(intent, true, result.data());

            context.session().log(intent, true, "Execução concluída.");

            return result;

        } catch (Exception e) {

            context.session().log(intent, false, e.getMessage());

            if (snapshotId != null) {
                context.rollback().restore(snapshotId);
            }

            context.feedbackLoop().evaluate(
                    intent,
                    false,
                    Map.of("error", e.getMessage())
            );

            throw e;
        }
    }
}