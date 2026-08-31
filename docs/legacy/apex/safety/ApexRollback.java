package apex.safety;

import apex.core.ApexException;

import java.io.IOException;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Sistema de rollback do APEX.
 * Cria snapshots de diretórios e restaura em caso de falha.
 * Agora com rastreamento correto do caminho original do snapshot.
 */
public class ApexRollback {

    private final Path rollbackRoot;

    /**
     * Mapeia snapshotId -> caminho original do diretório.
     */
    private final Map<String, Path> snapshotTargets = new HashMap<>();

    public ApexRollback(String projectRoot) {
        try {
            this.rollbackRoot = Paths.get(projectRoot, ".apex", "rollback").normalize().toAbsolutePath();
            Files.createDirectories(rollbackRoot);
        } catch (IOException e) {
            throw new ApexException(
                    ApexException.Tipo.SISTEMA,
                    "APX-RB-INIT",
                    "apex.rollback.init.falhou",
                    e.getMessage()
            );
        }
    }

    /**
     * Cria um snapshot completo do diretório alvo.
     *
     * @param targetPath Caminho do diretório a ser salvo
     * @return ID único do snapshot
     */
    public String createSnapshot(String targetPath) {
        try {
            Path target = Paths.get(targetPath).normalize().toAbsolutePath();
            if (!Files.exists(target)) {
                return null;
            }

            String snapshotId = UUID.randomUUID().toString();
            Path snapshotDir = rollbackRoot.resolve(snapshotId);

            Files.createDirectories(snapshotDir);

            // Salva o caminho original
            snapshotTargets.put(snapshotId, target);

            // Copia o diretório inteiro
            copyDirectory(target, snapshotDir.resolve(target.getFileName()));

            return snapshotId;

        } catch (Exception e) {
            throw new ApexException(
                    ApexException.Tipo.ROLLBACK_FALHOU,
                    "APX-RB-001",
                    "apex.rollback.snapshot.falhou",
                    e.getMessage()
            );
        }
    }

    /**
     * Restaura um snapshot previamente criado.
     */
    public void restore(String snapshotId) {
        try {
            Path snapshotDir = rollbackRoot.resolve(snapshotId);

            if (!Files.exists(snapshotDir)) {
                throw new ApexException(
                        ApexException.Tipo.ROLLBACK_FALHOU,
                        "APX-RB-404",
                        "apex.rollback.snapshot.nao.encontrado",
                        snapshotId
                );
            }

            Path originalTarget = snapshotTargets.get(snapshotId);
            if (originalTarget == null) {
                throw new ApexException(
                        ApexException.Tipo.ROLLBACK_FALHOU,
                        "APX-RB-NOTARGET",
                        "apex.rollback.target.nao.registrado",
                        snapshotId
                );
            }

            // Limpa o diretório original antes de restaurar
            if (Files.exists(originalTarget)) {
                deleteDirectory(originalTarget);
            }

            // Copia o snapshot de volta para o local original
            Path snapshotContent = snapshotDir.resolve(originalTarget.getFileName());
            copyDirectory(snapshotContent, originalTarget);

        } catch (Exception e) {
            throw new ApexException(
                    ApexException.Tipo.ROLLBACK_FALHOU,
                    "APX-RB-RESTORE",
                    "apex.rollback.restore.falhou",
                    e.getMessage()
            );
        }
    }

    private void copyDirectory(Path source, Path target) throws IOException {
        Files.walkFileTree(source, new SimpleFileVisitor<>() {

            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs)
                    throws IOException {

                Path relative = source.relativize(dir);
                Path newDir = target.resolve(relative);

                Files.createDirectories(newDir);

                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs)
                    throws IOException {

                Path relative = source.relativize(file);
                Path newFile = target.resolve(relative);

                Files.copy(file, newFile, StandardCopyOption.REPLACE_EXISTING);

                return FileVisitResult.CONTINUE;
            }
        });
    }

    private void deleteDirectory(Path path) throws IOException {
        if (!Files.exists(path)) return;

        Files.walkFileTree(path, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs)
                    throws IOException {
                Files.delete(file);
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult postVisitDirectory(Path dir, IOException exc)
                    throws IOException {
                Files.delete(dir);
                return FileVisitResult.CONTINUE;
            }
        });
    }
}