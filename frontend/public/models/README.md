# Modelos 3D da planta

Coloque aqui o modelo do **motor principal** com o nome exato:

```
motor.glb
```

Assim que o arquivo existir, a planta isométrica (`/plant/...`) troca o motor
estilizado (placeholder) pelo modelo real automaticamente — sem mudar código.

## Formato

O navegador só carrega **glTF binário** (`.glb`) ou `.gltf`. Os arquivos do
WEG W22 vieram em **Parasolid** (`.x_t`), que o navegador não abre. Converta
**apenas a carcaça do MTR-001** (≈ 132S/132M, confira na placa) para `.glb`:

- **Onshape** (grátis): importe o `.x_t` → *Export* → glTF.
- **Fusion 360** (grátis pessoal): importe o Parasolid → exporte OBJ/STL e
  converta para `.glb` (ex.: https://gltf.report ou Blender).
- **Blender**: importe o mesh (OBJ/STL) → *File ▸ Export ▸ glTF 2.0 (.glb)*.

Dicas: centralize o modelo na origem, deixe o eixo **Y para cima**, e
mantenha o `.glb` abaixo de ~10 MB (aplique *Draco* se precisar).
