package apex.handlers.impl;

import apex.core.ActionResult;
import apex.core.ApexContext;
import apex.handlers.AbstractHandler;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

/**
 * Handler que lista módulos existentes no projeto.
 */
public class ListModulesHandler extends AbstractHandler {

    public ListModulesHandler(ApexContext context) {
        super(context);
    }

    @Override
    public String getIntentName() {
        return "list_modules";
    }

    @Override
    public String getDescription() {
        return "Lista os módulos existentes no projeto.";
    }

    @Override
    public String[] getRequiredParams() {
        return new String[0];
    }

    @Override
    protected ActionResult performAction(Map<String, Object> params, ApexContext ctx) {

        Path modulesDir = Paths.get(ctx.projectRoot(), "modules");

        if (!Files.exists(modulesDir)) {
            return ActionResult.ok("Nenhum módulo encontrado.", Map.of("modules", List.of()), null);
        }

        List<Map<String, Object>> modules = new ArrayList<>();

        try (Stream<Path> stream = Files.list(modulesDir)) {
            stream.filter(Files::isDirectory).forEach(dir -> {

                String name = dir.getFileName().toString();
                String description = readDescription(dir);

                modules.add(Map.of(
                        "name", name,
                        "path", dir.toString(),
                        "description", description
                ));

                ctx.knowledge().registerEntity("module", name, dir.toString(), Map.of(
                        "description", description
                ));
            });
        } catch (IOException e) {
            return ActionResult.fail("Erro ao listar módulos: " + e.getMessage(), e.getMessage());
        }

        return ActionResult.ok(
                modules.size() + " módulos encontrados.",
                Map.of("modules", modules),
                null
        );
    }

    private String readDescription(Path moduleDir) {
        Path readme = moduleDir.resolve("README.md");
        try {
            return Files.exists(readme) ? Files.readString(readme) : "Sem descrição.";
        } catch (IOException e) {
            return "Erro ao ler descrição.";
        }
    }
}
