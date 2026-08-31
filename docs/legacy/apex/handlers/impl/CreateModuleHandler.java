package apex.handlers.impl;

import apex.core.ActionResult;
import apex.core.ApexContext;
import apex.handlers.AbstractHandler;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.Map;

/**
 * Handler de exemplo que cria um módulo dentro do projeto.
 * Demonstra rollback, simulação, escrita em disco e integração com o ApexKnowledge.
 */
public class CreateModuleHandler extends AbstractHandler {

    public CreateModuleHandler(ApexContext context) {
        super(context);
    }

    @Override
    public String getIntentName() {
        return "create_module";
    }

    @Override
    public String getDescription() {
        return "Cria um novo módulo no projeto.";
    }

    @Override
    public String[] getRequiredParams() {
        return new String[0];
    }

    @Override
    protected ActionResult performAction(Map<String, Object> params, ApexContext ctx) {
        String name = params.get("name") instanceof String value ? value : null;
        String description = params.get("description") instanceof String value ? value : null;

        if (name == null || name.isBlank()) {
            return ActionResult.fail("Nome do módulo é obrigatório.", "Nome do módulo é obrigatório.");
        }

        Path modulePath = Paths.get(ctx.projectRoot(), "modules", name);

        if (Files.exists(modulePath)) {
            return ActionResult.fail("O módulo '" + name + "' já existe.", "O módulo '" + name + "' já existe.");
        }

        Path modulesRoot = Paths.get(ctx.projectRoot(), "modules");
        String snapshotId = ctx.rollback().createSnapshot(modulesRoot.toString());

        try {
            Files.createDirectories(modulePath);

            Path readme = modulePath.resolve("README.md");
            Files.writeString(readme, description != null ? description : "Sem descrição.");

            Map<String, Object> metadata = new HashMap<>();
            if (description != null) {
                metadata.put("description", description);
            }

            ctx.knowledge().registerEntity("module", name, modulePath.toString(), metadata);

        } catch (IOException e) {
            if (snapshotId != null) {
                ctx.rollback().restore(snapshotId);
            }
            return ActionResult.fail("Erro ao criar módulo: " + e.getMessage(), e.getMessage());
        }

        Map<String, Object> resultData = new HashMap<>();
        resultData.put("name", name);
        resultData.put("description", description);

        return ActionResult.ok("Módulo criado com sucesso.", resultData, null);
    }
}