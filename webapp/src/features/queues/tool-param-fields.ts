import type { SchemaParamField } from "../../components/forms/schema-param-editor";
import type { SupportTicketToolsPayload } from "./api";

export type SupportToolItem = SupportTicketToolsPayload["tools"][number];

export function supportToolParamFields(tool: SupportToolItem | null): SchemaParamField[] {
  return (tool?.params_schema ?? []).map((field) => ({
    name: field.name,
    label: field.label ?? field.name,
    description: field.description,
    type: field.type,
    required: field.required,
    default: field.default,
  }));
}

export function validateSupportToolParams(
  selectedTool: SupportToolItem | null,
  selectedPresetId: string,
  toolParams: Record<string, unknown>,
) {
  if (!selectedTool) {
    throw new Error("Выберите инструмент.");
  }

  if (selectedPresetId.trim()) {
    const preset = selectedTool.presets.find((item) => item.preset_id === selectedPresetId.trim());
    return {
      presetId: selectedPresetId.trim(),
      params: preset?.params ?? {},
    };
  }

  const params: Record<string, unknown> = {};
  for (const field of selectedTool.params_schema) {
    const value = toolParams[field.name] ?? field.default;
    const isEmpty = value === null || value === undefined || value === "";
    if (isEmpty) {
      if (field.required) {
        throw new Error(`Заполните поле «${field.label ?? field.name}».`);
      }
      continue;
    }
    params[field.name] = value;
  }

  return {
    presetId: null,
    params,
  };
}
