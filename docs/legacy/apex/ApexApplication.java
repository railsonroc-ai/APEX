package apex;

import apex.bootstrap.IntentBootstrap;
import apex.context.ApexContext;

import java.nio.file.*;

public class ApexApplication {

    public static void main(String[] args) {

        // Define o caminho base do APEX
        String basePath = System.getProperty("user.dir");

        // Cria o contexto
        ApexContext ctx = new ApexContext(basePath);

        // Garante que a pasta /modules existe
        try {
            Files.createDirectories(Paths.get(basePath, "modules"));
        } catch (Exception e) {
            System.err.println("Erro ao criar diretório de módulos: " + e.getMessage());
        }

        // Registra todas as intents
        IntentBootstrap.registerAll(ctx);

        System.out.println("APEX inicializado com sucesso.");
    }
}
