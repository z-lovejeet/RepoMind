/**
 * RepoMind — File Tree Component
 *
 * Recursive directory tree in the sidebar.
 * Lazy-loads children when a directory is expanded.
 */

import { useState, useEffect, useCallback } from "react";
import { apiRequest } from "../../lib/api";
import type { FileNode } from "../../types";

interface FileTreeProps {
  repoId: string;
  onFileSelect: (filePath: string) => void;
}

interface TreeNodeProps {
  node: FileNode;
  path: string;
  repoId: string;
  selectedPath: string;
  onFileSelect: (filePath: string) => void;
}

function TreeNode({ node, path, repoId, selectedPath, onFileSelect }: TreeNodeProps) {
  const [expanded, setExpanded] = useState(false);
  const [children, setChildren] = useState<FileNode[]>([]);
  const [loading, setLoading] = useState(false);

  const fullPath = path ? `${path}/${node.name}` : node.name;
  const isDir = node.type === "directory";
  const isSelected = fullPath === selectedPath;

  const toggleDir = useCallback(async () => {
    if (!isDir) return;

    if (expanded) {
      setExpanded(false);
      return;
    }

    setLoading(true);
    try {
      const res = await apiRequest<{ path: string; children: FileNode[] }>(
        `/api/repos/${repoId}/files?path=${encodeURIComponent(fullPath)}`
      );
      setChildren(res.data.children);
      setExpanded(true);
    } catch {
      // Silently fail — directory might be empty
    } finally {
      setLoading(false);
    }
  }, [isDir, expanded, repoId, fullPath]);

  const handleClick = () => {
    if (isDir) {
      toggleDir();
    } else {
      onFileSelect(fullPath);
    }
  };

  const icon = isDir ? (expanded ? "📂" : "📁") : "📄";

  return (
    <div className="file-tree-node">
      <button
        className={`file-tree-item ${isDir ? "file-tree-dir" : "file-tree-file"} ${
          isSelected ? "file-tree-selected" : ""
        }`}
        onClick={handleClick}
      >
        {isDir && (
          <span className={`file-tree-chevron ${expanded ? "expanded" : ""}`}>
            ▶
          </span>
        )}
        <span className="file-tree-icon">{icon}</span>
        <span className="file-tree-name">{node.name}</span>
        {loading && <span className="file-tree-loading">…</span>}
      </button>

      {expanded && children.length > 0 && (
        <div className="file-tree-children">
          {children.map((child) => (
            <TreeNode
              key={child.name}
              node={child}
              path={fullPath}
              repoId={repoId}
              selectedPath={selectedPath}
              onFileSelect={onFileSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function FileTree({ repoId, onFileSelect }: FileTreeProps) {
  const [rootChildren, setRootChildren] = useState<FileNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedPath, setSelectedPath] = useState("");

  useEffect(() => {
    async function loadRoot() {
      try {
        const res = await apiRequest<{ path: string; children: FileNode[] }>(
          `/api/repos/${repoId}/files`
        );
        setRootChildren(res.data.children);
      } catch {
        // Silently fail
      } finally {
        setLoading(false);
      }
    }
    loadRoot();
  }, [repoId]);

  const handleSelect = (path: string) => {
    setSelectedPath(path);
    onFileSelect(path);
  };

  if (loading) {
    return (
      <div className="file-tree">
        <p className="file-tree-loading-text">Loading files…</p>
      </div>
    );
  }

  if (rootChildren.length === 0) {
    return (
      <div className="file-tree">
        <p className="file-tree-empty">No files found</p>
      </div>
    );
  }

  return (
    <div className="file-tree">
      {rootChildren.map((node) => (
        <TreeNode
          key={node.name}
          node={node}
          path=""
          repoId={repoId}
          selectedPath={selectedPath}
          onFileSelect={handleSelect}
        />
      ))}
    </div>
  );
}
