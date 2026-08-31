package apex.bootstrap;

import apex.core.ApexContext;
import apex.handlers.impl.CreateModuleHandler;
import apex.handlers.impl.DeleteModuleHandler;
import apex.handlers.impl.EditModuleHandler;
import apex.handlers.impl.ExecuteIntentHandler;
import apex.handlers.impl.ListIntentsHandler;
import apex.handlers.impl.ListModulesHandler;

public final class IntentBootstrap {

    private IntentBootstrap() {
    }

    public static void registerAll(ApexContext ctx) {
        ctx.intentRegistry().register(new CreateModuleHandler(ctx));
        ctx.intentRegistry().register(new ListModulesHandler(ctx));
        ctx.intentRegistry().register(new EditModuleHandler(ctx));
        ctx.intentRegistry().register(new DeleteModuleHandler(ctx));
        ctx.intentRegistry().register(new ListIntentsHandler(ctx));
        ctx.intentRegistry().register(new ExecuteIntentHandler(ctx));
    }
}
