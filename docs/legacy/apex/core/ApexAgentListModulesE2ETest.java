package apex.core;

import apex.bootstrap.IntentBootstrap;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

public class ApexAgentListModulesE2ETest {

    public static void main(String[] args) throws IOException {
        Path tempRoot = Files.createTempDirectory("apex-list-modules-e2e-");

        try {
            Path modulesDir = tempRoot.resolve("modules");
            Path moduleA = modulesDir.resolve("module-a");
            Path moduleB = modulesDir.resolve("module-b");

            Files.createDirectories(moduleA);
            Files.createDirectories(moduleB);

            Files.writeString(moduleA.resolve("README.md"), "Módulo A");
            Files.writeString(moduleB.resolve("README.md"), "Módulo B");

            ApexContext context = new ApexContext(tempRoot.toString(), false, true);
            IntentBootstrap.registerAll(context);
            ApexAgent agent = new ApexAgent(context);

            ActionResult result = agent.execute("list_modules", Map.of());

            if (!result.isSuccess()) {
                throw new IllegalStateException("Execução deveria ter sucesso, mas falhou: " + result.error());
            }

            Object modulesRaw = result.data().get("modules");
            if (!(modulesRaw instanceof List<?> modules)) {
                throw new IllegalStateException("Campo 'modules' ausente ou inválido no resultado.");
            }

            if (modules.size() != 2) {
                throw new IllegalStateException("Quantidade esperada de módulos: 2, recebido: " + modules.size());
            }

            boolean hasModuleA = modules.stream()
                    .filter(Map.class::isInstance)
                    .map(Map.class::cast)
                    .anyMatch(item -> "module-a".equals(String.valueOf(item.get("name"))));

            boolean hasModuleB = modules.stream()
                    .filter(Map.class::isInstance)
                    .map(Map.class::cast)
                    .anyMatch(item -> "module-b".equals(String.valueOf(item.get("name"))));

            if (!hasModuleA || !hasModuleB) {
                throw new IllegalStateException("Lista de módulos não contém os nomes esperados.");
            }

            System.out.println("OK: execute(list_modules) retornou 2 módulos esperados.");

        } finally {
            deleteRecursively(tempRoot);
        }
    }

    private static void deleteRecursively(Path root) throws IOException {
        if (!Files.exists(root)) {
            return;
        }

        try (Stream<Path> walk = Files.walk(root)) {
            walk.sorted((a, b) -> b.compareTo(a))
                    .forEach(path -> {
                        try {
                            Files.deleteIfExists(path);
                        } catch (IOException ignored) {
                        }
                    });
        }
    }
}
