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
 * Handler que edita um módulo existente do projeto.
 */
public class EditModuleHandler extends AbstractHandler {

    public EditModuleHandler(ApexContext context) {
        super(context);
    }

    @Override
    public String getIntentName() {
        return "edit_module";
    }

    @Override
    public String getDescription() {
        return "Edita nome e/ou descrição de um módulo existente.";
    }

    @Override
    public String[] getRequiredParams() {
        return new String[0];
    }

    @Override
    protected ActionResult performAction(Map<String, Object> params, ApexContext ctx) {

        String name = params.get("name") instanceof String value ? value : null;
        String newName = params.get("newName") instanceof String value ? value : null;
        String description = params.get("description") instanceof String value ? value : null;

        if (name == null || name.isBlank()) {
            return ActionResult.fail("Nome do módulo é obrigatório.", "Nome do módulo é obrigatório.");
        }

        boolean hasNewName = newName != null && !newName.isBlank();
        boolean hasDescription = description != null && !description.isBlank();

        if (!hasNewName && !hasDescription) {
            return ActionResult.fail("Nenhuma alteração foi solicitada.", "Nenhuma alteração foi solicitada.");
        }

        Path modulePath = Paths.get(ctx.projectRoot(), "modules", name);

        if (!Files.exists(modulePath)) {
            return ActionResult.fail("Módulo '" + name + "' não existe.", "Módulo '" + name + "' não existe.");
        }

        Path modulesRoot = Paths.get(ctx.projectRoot(), "modules");
        String snapshotId = ctx.rollback().createSnapshot(modulesRoot.toString());

        String finalName = name;

        try {
            if (hasNewName) {
                Path newPath = modulePath.resolveSibling(newName);

                if (!newPath.equals(modulePath) && Files.exists(newPath)) {
                    return ActionResult.fail(
                            "Já existe um módulo com o nome '" + newName + "'.",
                            "Já existe um módulo com o nome '" + newName + "'."
                    );
                }

                Files.move(modulePath, newPath);
                modulePath = newPath;
                finalName = newName;
            }

            if (hasDescription) {
                Path readme = modulePath.resolve("README.md");
                Files.writeString(readme, description);
            }

        } catch (IOException e) {
            if (snapshotId != null) {
                ctx.rollback().restore(snapshotId);
            }
            return ActionResult.fail("Erro ao editar módulo: " + e.getMessage(), e.getMessage());
        }

        ctx.knowledge().addInsight(
                "module_edited",
                Map.of(
                        "oldName", name,
                        "name", finalName,
                        "path", modulePath.toString()
                ),
                "edited"
        );

        Map<String, Object> resultData = new HashMap<>();
        resultData.put("name", finalName);
        resultData.put("description", description);

        return ActionResult.ok("Módulo atualizado.", resultData, null);
    }
}
