import * as Dialog from "@radix-ui/react-dialog";
import { zodResolver } from "@hookform/resolvers/zod";
import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "./Button";
import { FieldLabel } from "./FieldLabel";
import styles from "./RenameDialog.module.css";

const metadataSchema = z.object({
  title: z.string().trim().min(1, "Title is required.").max(200, "Title must be 200 characters or fewer."),
  description: z.string().max(1_000, "Description must be 1,000 characters or fewer.").optional(),
});

type MetadataForm = z.infer<typeof metadataSchema>;

export function RenameDialog({
  currentTitle,
  currentDescription,
  onApply,
}: {
  currentTitle: string;
  currentDescription: string;
  onApply: (value: MetadataForm) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [dirtyPrompt, setDirtyPrompt] = useState(false);
  const { register, handleSubmit, reset, formState: { errors, isDirty, isSubmitting } } = useForm<MetadataForm>({
    resolver: zodResolver(metadataSchema),
    defaultValues: { title: currentTitle, description: currentDescription },
    mode: "onBlur",
  });

  useEffect(() => {
    if (!open) reset({ title: currentTitle, description: currentDescription });
  }, [currentDescription, currentTitle, open, reset]);

  const requestClose = (nextOpen: boolean) => {
    if (!nextOpen && isDirty) {
      setDirtyPrompt(true);
      setOpen(true);
      return;
    }
    setDirtyPrompt(false);
    setOpen(nextOpen);
  };

  const discard = () => {
    reset({ title: currentTitle, description: currentDescription });
    setDirtyPrompt(false);
    setOpen(false);
  };

  return (
    <Dialog.Root open={open} onOpenChange={requestClose}>
      <Dialog.Trigger asChild><Button size="sm">Edit display metadata</Button></Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className={styles.overlay} />
        <Dialog.Content className={styles.content} aria-describedby="rename-description">
          <div className={styles.heading}>
            <div><Dialog.Title>Edit display metadata</Dialog.Title><Dialog.Description id="rename-description">This prototype patch keeps the same stored ID and links. It is in-memory only.</Dialog.Description></div>
            <Dialog.Close asChild><button className={styles.close} type="button" aria-label="Close metadata dialog"><X size={18} /></button></Dialog.Close>
          </div>
          <form onSubmit={handleSubmit(async (value) => { await onApply(value); setDirtyPrompt(false); setOpen(false); })}>
            <div className={styles.field}><FieldLabel htmlFor="metadata-title" hint="1–200 characters">Title</FieldLabel><input id="metadata-title" {...register("title")} aria-invalid={Boolean(errors.title)} aria-describedby={errors.title ? "metadata-title-error" : undefined} />{errors.title ? <p id="metadata-title-error" className={styles.error} role="alert">{errors.title.message}</p> : null}</div>
            <div className={styles.field}><FieldLabel htmlFor="metadata-description" hint="Optional">Description</FieldLabel><textarea id="metadata-description" rows={4} {...register("description")} aria-invalid={Boolean(errors.description)} aria-describedby={errors.description ? "metadata-description-error" : undefined} />{errors.description ? <p id="metadata-description-error" className={styles.error} role="alert">{errors.description.message}</p> : null}</div>
            {dirtyPrompt ? <div className={styles.dirtyPrompt} role="alert"><strong>Unsaved draft</strong><span>Close or Escape keeps this draft until you choose.</span><div><Button size="sm" type="button" onClick={() => setDirtyPrompt(false)}>Continue editing</Button><Button size="sm" variant="danger" type="button" onClick={discard}>Discard draft</Button></div></div> : null}
            <div className={styles.actions}><Dialog.Close asChild><Button type="button">Cancel</Button></Dialog.Close><Button type="submit" variant="primary" disabled={isSubmitting}>{isSubmitting ? "Applying…" : "Apply example"}</Button></div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
