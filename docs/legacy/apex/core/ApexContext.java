package apex.core;

import apex.feedback.ApexFeedbackLoop;
import apex.memory.ApexKnowledge;
import apex.safety.ApexRollback;

import java.io.Serial;
import java.io.Serializable;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Objects;

/**
 * Contexto principal do APEX.
 * Reúne todos os componentes necessários para execução de handlers.
 * Agora com validação defensiva e normalização de path.
 */
public class ApexContext implements Serializable {

    @Serial
    private static final long serialVersionUID = 20260303L;

    private final String basePath;
    private final String projectRoot;
    private final boolean dryRun;
    private final boolean rollbackEnabled;

    private final ApexSession session;
    private final ApexKnowledge knowledge;
    private final ApexRollback rollback;
    private final ApexFeedbackLoop feedbackLoop;
    private final ModuleRegistry moduleRegistry = new ModuleRegistry();
    private final IntentRegistry intentRegistry = new IntentRegistry();

    public ApexContext(String basePath) {
        this(basePath, false, true);
    }

    public ApexContext(String projectRoot, boolean dryRun, boolean rollbackEnabled) {

        Objects.requireNonNull(projectRoot, "projectRoot não pode ser nulo");

        Path normalized = Paths.get(projectRoot).normalize().toAbsolutePath();
        this.projectRoot = normalized.toString();
        this.basePath = this.projectRoot;

        try {
            Files.createDirectories(Paths.get(this.projectRoot, "modules"));
        } catch (IOException e) {
            throw new ApexException(
                    ApexException.Tipo.SISTEMA,
                    "APX-CTX-MODDIR",
                    "apex.context.modules.dir.falhou",
                    e.getMessage()
            );
        }

        this.dryRun = dryRun;
        this.rollbackEnabled = rollbackEnabled;

        this.session = new ApexSession();
        this.knowledge = new ApexKnowledge();
        this.rollback = new ApexRollback(this.projectRoot);
        this.feedbackLoop = new ApexFeedbackLoop(this);
    }

    public String projectRoot() {
        return projectRoot;
    }

    public String getBasePath() {
        return basePath;
    }

    public boolean isDryRun() {
        return dryRun;
    }

    public boolean isRollbackEnabled() {
        return rollbackEnabled;
    }

    public ApexSession session() {
        return session;
    }

    public ApexKnowledge knowledge() {
        return knowledge;
    }

    public ApexRollback rollback() {
        return rollback;
    }

    public ApexFeedbackLoop feedbackLoop() {
        return feedbackLoop;
    }

    public ModuleRegistry moduleRegistry() {
        return moduleRegistry;
    }

    public IntentRegistry intentRegistry() {
        return intentRegistry;
    }
}