package apex.handlers.impl;

import apex.core.ActionResult;
import apex.core.ApexContext;
import apex.handlers.AbstractHandler;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Comparator;
import java.util.Map;
import java.util.stream.Stream;

/**
 * Handler que remove um módulo existente do projeto.
 */
public class DeleteModuleHandler extends AbstractHandler {

    public DeleteModuleHandler(ApexContext context) {
        super(context);
    }

    @Override
    public String getIntentName() {
        return "delete_module";
    }

    @Override
    public String getDescription() {
        return "Remove um módulo existente do projeto.";
    }

    @Override
    public String[] getRequiredParams() {
        return new String[0];
    }

    @Override
    protected ActionResult performAction(Map<String, Object> params, ApexContext ctx) {

        String name = params.get("name") instanceof String value ? value : null;
        if (name == null || name.isBlank()) {
            return ActionResult.fail("Nome do módulo é obrigatório.", "Nome do módulo é obrigatório.");
        }

        Path modulePath = Paths.get(ctx.projectRoot(), "modules", name);

        if (!Files.exists(modulePath)) {
            return ActionResult.fail("Módulo '" + name + "' não existe.", "Módulo '" + name + "' não existe.");
        }

        String snapshotId = ctx.rollback().createSnapshot(modulePath.toString());

        try {
            deleteDirectory(modulePath);
        } catch (IOException e) {
            if (snapshotId != null) {
                ctx.rollback().restore(snapshotId);
            }
            return ActionResult.fail("Erro ao excluir módulo: " + e.getMessage(), e.getMessage());
        }

        ctx.knowledge().addInsight(
                "module_deleted",
                Map.of(
                        "name", name,
                        "path", modulePath.toString()
                ),
                "deleted"
        );

        return ActionResult.ok(
                "Módulo '" + name + "' removido com sucesso.",
                Map.of("name", name, "deleted", true),
                null
        );
    }

    private void deleteDirectory(Path path) throws IOException {
        try (Stream<Path> walk = Files.walk(path)) {
            for (Path currentPath : walk.sorted(Comparator.reverseOrder()).toList()) {
                Files.deleteIfExists(currentPath);
            }
        }
    }
}
