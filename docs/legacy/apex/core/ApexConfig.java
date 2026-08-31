package apex.core;

import java.io.Serial;
import java.io.Serializable;

/**
 * Configurações gerais do APEX.
 * Pode ser expandida futuramente para incluir:
 * - níveis de log
 * - configurações de segurança
 * - parâmetros de execução
 * - integração com serviços externos
 */
public class ApexConfig implements Serializable {

    @Serial
    private static final long serialVersionUID = 20260303L;

    private final boolean rollbackEnabled;
    private final boolean dryRun;

    public ApexConfig(boolean rollbackEnabled, boolean dryRun) {
        this.rollbackEnabled = rollbackEnabled;
        this.dryRun = dryRun;
    }

    public boolean isRollbackEnabled() {
        return rollbackEnabled;
    }

    public boolean isDryRun() {
        return dryRun;
    }
}