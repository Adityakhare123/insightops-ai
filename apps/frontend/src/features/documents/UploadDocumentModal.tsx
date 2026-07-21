import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";

import {
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";

import { ApiError } from "../../api/client";
import { uploadDocument } from "./documentsApi";

import type {
  DocumentRead,
} from "../../types/document";


const MAX_FILE_SIZE_BYTES =
  25 * 1024 * 1024;

const ALLOWED_EXTENSIONS = new Set([
  ".pdf",
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
  ".csv",
  ".xls",
  ".xlsx",
]);


interface UploadDocumentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploaded?: (
    document: DocumentRead,
  ) => void;
}


function formatFileSize(
  sizeInBytes: number,
): string {
  if (sizeInBytes < 1024) {
    return `${sizeInBytes} B`;
  }

  const sizeInKilobytes =
    sizeInBytes / 1024;

  if (sizeInKilobytes < 1024) {
    return `${sizeInKilobytes.toFixed(1)} KB`;
  }

  const sizeInMegabytes =
    sizeInKilobytes / 1024;

  return `${sizeInMegabytes.toFixed(2)} MB`;
}


function getFileExtension(
  filename: string,
): string {
  const extensionIndex =
    filename.lastIndexOf(".");

  if (extensionIndex < 0) {
    return "";
  }

  return filename
    .slice(extensionIndex)
    .toLowerCase();
}


function validateSelectedFile(
  file: File,
): string | null {
  if (file.size <= 0) {
    return "The selected file is empty.";
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    return "The selected file exceeds the 25 MB limit.";
  }

  const extension = getFileExtension(
    file.name,
  );

  if (!ALLOWED_EXTENSIONS.has(extension)) {
    return (
      "Unsupported file type. Select a PDF, image, "
      + "CSV, XLS, or XLSX file."
    );
  }

  return null;
}


function getUploadErrorMessage(
  error: unknown,
): string {
  if (error instanceof ApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return (
    "The document could not be uploaded. "
    + "Please try again."
  );
}


export default function UploadDocumentModal({
  isOpen,
  onClose,
  onUploaded,
}: UploadDocumentModalProps) {
  const queryClient = useQueryClient();

  const fileInputReference =
    useRef<HTMLInputElement | null>(null);

  const [selectedFile, setSelectedFile] =
    useState<File | null>(null);

  const [validationError, setValidationError] =
    useState<string | null>(null);

  const [isDragging, setIsDragging] =
    useState(false);

  const uploadMutation = useMutation({
    mutationFn: uploadDocument,

    onSuccess: async (response) => {
      await queryClient.invalidateQueries({
        queryKey: ["documents"],
      });

      onUploaded?.(response.document);
    },
  });


  function resetModalState(): void {
    setSelectedFile(null);
    setValidationError(null);
    setIsDragging(false);
    uploadMutation.reset();

    if (fileInputReference.current) {
      fileInputReference.current.value = "";
    }
  }


  function handleClose(): void {
    if (uploadMutation.isPending) {
      return;
    }

    resetModalState();
    onClose();
  }


  function selectFile(
    file: File | null,
  ): void {
    uploadMutation.reset();
    setValidationError(null);

    if (!file) {
      setSelectedFile(null);
      return;
    }

    const fileValidationError =
      validateSelectedFile(file);

    if (fileValidationError) {
      setSelectedFile(null);
      setValidationError(
        fileValidationError,
      );

      return;
    }

    setSelectedFile(file);
  }


  function handleFileInputChange(
    event: ChangeEvent<HTMLInputElement>,
  ): void {
    const file =
      event.target.files?.[0] ?? null;

    selectFile(file);
  }


  function handleDragOver(
    event: DragEvent<HTMLDivElement>,
  ): void {
    event.preventDefault();

    if (!uploadMutation.isPending) {
      setIsDragging(true);
    }
  }


  function handleDragLeave(
    event: DragEvent<HTMLDivElement>,
  ): void {
    event.preventDefault();
    setIsDragging(false);
  }


  function handleDrop(
    event: DragEvent<HTMLDivElement>,
  ): void {
    event.preventDefault();
    setIsDragging(false);

    if (uploadMutation.isPending) {
      return;
    }

    const file =
      event.dataTransfer.files?.[0] ?? null;

    selectFile(file);
  }


  function openFilePicker(): void {
    if (!uploadMutation.isPending) {
      fileInputReference.current?.click();
    }
  }


  function handleUpload(): void {
    if (!selectedFile) {
      setValidationError(
        "Select a document before uploading.",
      );

      return;
    }

    uploadMutation.mutate(selectedFile);
  }


  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function handleKeyDown(
      event: KeyboardEvent,
    ): void {
      if (event.key === "Escape") {
        handleClose();
      }
    }

    window.addEventListener(
      "keydown",
      handleKeyDown,
    );

    return () => {
      window.removeEventListener(
        "keydown",
        handleKeyDown,
      );
    };
  });


  if (!isOpen) {
    return null;
  }


  const uploadError = uploadMutation.isError
    ? getUploadErrorMessage(
        uploadMutation.error,
      )
    : null;

  const uploadedDocument =
    uploadMutation.data?.document ?? null;


  return (
    <div
      className="upload-modal-overlay"
      role="presentation"
      onMouseDown={(event) => {
        if (
          event.target === event.currentTarget
        ) {
          handleClose();
        }
      }}
    >
      <section
        className="upload-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-modal-title"
      >
        <header className="upload-modal-header">
          <div>
            <p className="dashboard-panel-label">
              Document ingestion
            </p>

            <h2 id="upload-modal-title">
              Upload a document
            </h2>

            <p>
              Add a document to the current workspace.
              The original file will be stored securely
              in MinIO.
            </p>
          </div>

          <button
            className="upload-modal-close"
            type="button"
            onClick={handleClose}
            disabled={uploadMutation.isPending}
            aria-label="Close upload dialog"
          >
            ×
          </button>
        </header>

        {!uploadedDocument && (
          <>
            <input
              ref={fileInputReference}
              className="upload-file-input"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp,.csv,.xls,.xlsx"
              onChange={handleFileInputChange}
              disabled={uploadMutation.isPending}
            />

            <div
              className={[
                "upload-drop-zone",
                isDragging
                  ? "dragging"
                  : "",
                selectedFile
                  ? "selected"
                  : "",
              ]
                .filter(Boolean)
                .join(" ")}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <div className="upload-drop-icon">
                ↑
              </div>

              {selectedFile ? (
                <div className="selected-file-details">
                  <strong>
                    {selectedFile.name}
                  </strong>

                  <span>
                    {formatFileSize(
                      selectedFile.size,
                    )}
                  </span>

                  <button
                    type="button"
                    onClick={openFilePicker}
                    disabled={
                      uploadMutation.isPending
                    }
                  >
                    Choose another file
                  </button>
                </div>
              ) : (
                <>
                  <strong>
                    Drop a document here
                  </strong>

                  <p>
                    or select a file from your computer
                  </p>

                  <button
                    type="button"
                    onClick={openFilePicker}
                  >
                    Browse files
                  </button>
                </>
              )}
            </div>

            <div className="upload-requirements">
              <span>
                PDF, PNG, JPG, WEBP, CSV, XLS, XLSX
              </span>

              <span>Maximum 25 MB</span>
            </div>

            {(validationError || uploadError) && (
              <div
                className="upload-message error"
                role="alert"
              >
                {validationError ?? uploadError}
              </div>
            )}

            <footer className="upload-modal-actions">
              <button
                className="upload-secondary-action"
                type="button"
                onClick={handleClose}
                disabled={uploadMutation.isPending}
              >
                Cancel
              </button>

              <button
                className="upload-primary-action"
                type="button"
                onClick={handleUpload}
                disabled={
                  !selectedFile
                  || uploadMutation.isPending
                }
              >
                {uploadMutation.isPending
                  ? "Uploading…"
                  : "Upload document"}
              </button>
            </footer>
          </>
        )}

        {uploadedDocument && (
          <div className="upload-success">
            <div className="upload-success-icon">
              ✓
            </div>

            <h3>Upload complete</h3>

            <p>
              The document was stored successfully
              and added to your workspace.
            </p>

            <div className="upload-success-document">
              <strong>
                {uploadedDocument.original_filename}
              </strong>

              <span>
                {formatFileSize(
                  uploadedDocument.file_size_bytes,
                )}
                {" · "}
                {uploadedDocument.document_type
                  ?? "document"}
              </span>
            </div>

            <button
              className="upload-primary-action"
              type="button"
              onClick={handleClose}
            >
              Done
            </button>
          </div>
        )}
      </section>
    </div>
  );
}