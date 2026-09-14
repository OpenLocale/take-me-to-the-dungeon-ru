using AssetsTools.NET;
using AssetsTools.NET.Extra;
using AssetsTools.NET.Texture;

if (args.Length != 3)
{
    Console.Error.WriteLine("Usage: font-importer <cjkru asset bundle> <input resources.assets> <output resources.assets>");
    return 2;
}

var bundlePath = Path.GetFullPath(args[0]);
var inputPath = Path.GetFullPath(args[1]);
var outputPath = Path.GetFullPath(args[2]);
var manager = new AssetsManager();

try
{
    var bundle = manager.LoadBundleFile(bundlePath, false);
    var source = Enumerable.Range(0, bundle.file.BlockAndDirInfo.DirectoryInfos.Count)
        .Select(index => manager.LoadAssetsFileFromBundle(bundle, index, false))
        .FirstOrDefault(file => file != null);
    if (source == null)
        throw new InvalidOperationException("The generated bundle contains no assets file");

    var target = manager.LoadAssetsFile(inputPath, false);
    var sourceFontInfo = FindByName(manager, source, AssetClassID.MonoBehaviour, "CJKtc RU SDF");
    var sourceFontField = manager.GetBaseField(source, sourceFontInfo);
    var sourceFamily = sourceFontField["m_FaceInfo"]["m_FamilyName"].AsString;
    var sourceStyle = sourceFontField["m_FaceInfo"]["m_StyleName"].AsString;
    if (sourceFamily != "Noto Sans" || sourceStyle != "Regular")
        throw new InvalidOperationException(
            $"Expected Noto Sans/Regular fallback, found {sourceFamily}/{sourceStyle}");
    var sourceMaterialId = PPtrPath(sourceFontField["material"]);
    var sourceTextureId = PPtrPath(sourceFontField["m_AtlasTextures"]["Array"].Children.Single());
    var characterSetPath = Path.GetFullPath(Path.Combine(
        Path.GetDirectoryName(bundlePath)!, "..", "Assets", "cyrillic_chars.txt"));
    var requiredCodepoints = File.ReadAllText(characterSetPath)
        .Select(character => (uint)character)
        .ToHashSet();
    var generatedCodepoints = sourceFontField["m_CharacterTable"]["Array"].Children
        .Select(entry => entry["m_Unicode"].AsUInt)
        .ToHashSet();
    var missingCodepoints = requiredCodepoints.Except(generatedCodepoints).ToArray();
    if (missingCodepoints.Length != 0)
        throw new InvalidOperationException(
            "Generated TMP character table is incomplete: " +
            string.Join(", ", missingCodepoints.Select(codepoint => $"U+{codepoint:X4}")));
    var sourceFontFileIds = new[]
    {
        PPtrPath(sourceFontField["m_SourceFontFile_EditorRef"]),
        PPtrPath(sourceFontField["m_SourceFontFile"]),
    }.Where(id => id != 0).Distinct().ToArray();

    var sourceMaterialInfo = source.file.GetAssetInfo(sourceMaterialId)
        ?? throw new InvalidOperationException("Generated TMP material was not found");
    var sourceTextureInfo = source.file.GetAssetInfo(sourceTextureId)
        ?? throw new InvalidOperationException("Generated TMP atlas texture was not found");
    var sourceMaterialField = manager.GetBaseField(source, sourceMaterialInfo);
    var sourceTextureField = manager.GetBaseField(source, sourceTextureInfo);

    var targetCjkInfo = target.file.GetAssetInfo(225370)
        ?? throw new InvalidOperationException("Target CJKtc SDF (225370) was not found");
    var targetMaterialInfo = target.file.GetAssetInfo(608)
        ?? throw new InvalidOperationException("Target CJKtc material (608) was not found");
    var targetTextureInfo = target.file.GetAssetInfo(4022)
        ?? throw new InvalidOperationException("Target CJKtc atlas (4022) was not found");

    var fontTemplate = TemplateFromSourceType(source, sourceFontInfo);
    var materialTemplate = TemplateFromSourceType(source, sourceMaterialInfo);
    var targetCjkField = ReadWithTemplate(fontTemplate, ReadRaw(target.file, targetCjkInfo));
    var targetMaterialField = ReadWithTemplate(materialTemplate, ReadRaw(target.file, targetMaterialInfo));

    var nextPathId = target.file.Metadata.AssetInfos.Max(info => info.PathId) + 1;
    var newFontId = nextPathId++;
    var newMaterialId = nextPathId++;
    var newTextureId = nextPathId;

    CopyPPtr(targetCjkField["m_Script"], sourceFontField["m_Script"]);
    CopyPPtr(targetMaterialField["m_Shader"], sourceMaterialField["m_Shader"]);
    sourceFontField["m_Name"].AsString = "CJKtc RU SDF";
    sourceMaterialField["m_Name"].AsString = "CJKtc RU SDF Material";

    var pointerMap = new Dictionary<long, long>
    {
        [sourceMaterialId] = newMaterialId,
        [sourceTextureId] = newTextureId,
    };
    foreach (var sourceFontFileId in sourceFontFileIds)
        pointerMap[sourceFontFileId] = 9713;
    RewriteLocalPointers(sourceFontField, pointerMap);
    RewriteLocalPointers(sourceMaterialField, pointerMap);
    SetPPtr(sourceFontField["m_SourceFontFile"], 0, 9713);
    if (!sourceFontField["m_SourceFontFile_EditorRef"].IsDummy)
        SetPPtr(sourceFontField["m_SourceFontFile_EditorRef"], 0, 9713);

    var texture = TextureFile.ReadTextureFile(sourceTextureField);
    var textureBytes = texture.FillPictureData(source)
        ?? throw new InvalidOperationException("Could not read generated atlas texture data");
    if (textureBytes.Length == 0)
        throw new InvalidOperationException("Generated atlas texture is empty");
    texture.m_Name = "CJKtc RU SDF Atlas";
    texture.WriteTo(sourceTextureField);

    var fallbackTable = targetCjkField["m_FallbackFontAssetTable"]["Array"];
    if (fallbackTable.IsDummy)
        throw new InvalidOperationException("CJKtc SDF fallback table could not be parsed");
    if (fallbackTable.Children.Any(field => PPtrPath(field) == newFontId))
        throw new InvalidOperationException("Generated fallback is already linked");
    var fallback = ValueBuilder.DefaultValueFieldFromArrayTemplate(fallbackTable)
        ?? throw new InvalidOperationException("Could not create fallback table entry");
    SetPPtr(fallback, 0, newFontId);
    fallbackTable.Children.Add(fallback);
    fallbackTable.AsArray = new AssetTypeArrayInfo(fallbackTable.Children.Count);

    AddLike(target.file, targetCjkInfo, newFontId, sourceFontField.WriteToByteArray());
    AddLike(target.file, targetMaterialInfo, newMaterialId, sourceMaterialField.WriteToByteArray());
    AddLike(target.file, targetTextureInfo, newTextureId, sourceTextureField.WriteToByteArray());
    targetCjkInfo.SetNewData(targetCjkField);

    Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
    using var writer = new AssetsFileWriter(outputPath);
    target.file.Write(writer);

    Console.WriteLine($"Added static fallback font {newFontId}, material {newMaterialId}, texture {newTextureId}");
    Console.WriteLine($"Validated fallback face: {sourceFamily}/{sourceStyle}");
    Console.WriteLine($"Embedded atlas bytes: {textureBytes.Length}");
    Console.WriteLine($"Validated character table: {requiredCodepoints.Count} required codepoints");
    return 0;
}
finally
{
    manager.UnloadAll();
}

static AssetFileInfo FindByName(
    AssetsManager manager,
    AssetsFileInstance file,
    AssetClassID type,
    string name)
{
    foreach (var info in file.file.GetAssetsOfType(type))
    {
        var field = manager.GetBaseField(file, info);
        if (!field["m_Name"].IsDummy && field["m_Name"].AsString == name)
            return info;
    }
    throw new InvalidOperationException($"{type} named '{name}' was not found");
}

static AssetTypeTemplateField TemplateFromSourceType(AssetsFileInstance file, AssetFileInfo info)
{
    var type = file.file.Metadata.TypeTreeTypes[info.TypeIdOrIndex];
    var template = new AssetTypeTemplateField();
    template.FromTypeTree(type);
    return template;
}

static AssetTypeValueField ReadWithTemplate(AssetTypeTemplateField template, byte[] bytes)
{
    using var stream = new MemoryStream(bytes, false);
    using var reader = new AssetsFileReader(stream);
    return template.MakeValue(reader);
}

static byte[] ReadRaw(AssetsFile file, AssetFileInfo info)
{
    file.Reader.Position = info.GetAbsoluteByteOffset(file);
    return file.Reader.ReadBytes(checked((int)info.ByteSize));
}

static void AddLike(AssetsFile file, AssetFileInfo template, long pathId, byte[] bytes)
{
    var info = new AssetFileInfo
    {
        PathId = pathId,
        TypeIdOrIndex = template.TypeIdOrIndex,
        OldTypeId = template.OldTypeId,
        ScriptTypeIndex = template.ScriptTypeIndex,
        Stripped = template.Stripped,
        TypeId = template.TypeId,
    };
    info.SetNewData(bytes);
    file.Metadata.AddAssetInfo(info);
}

static void RewriteLocalPointers(AssetTypeValueField field, IReadOnlyDictionary<long, long> map)
{
    var fileId = field["m_FileID"];
    var pathId = field["m_PathID"];
    if (!fileId.IsDummy && !pathId.IsDummy && fileId.AsInt == 0 && map.TryGetValue(pathId.AsLong, out var replacement))
        SetPPtr(field, 0, replacement);
    foreach (var child in field.Children)
        RewriteLocalPointers(child, map);
}

static long PPtrPath(AssetTypeValueField pointer)
{
    if (pointer.IsDummy)
        return 0;
    var path = pointer["m_PathID"];
    return path.IsDummy ? 0 : path.AsLong;
}

static void CopyPPtr(AssetTypeValueField source, AssetTypeValueField destination)
{
    SetPPtr(destination, source["m_FileID"].AsInt, source["m_PathID"].AsLong);
}

static void SetPPtr(AssetTypeValueField pointer, int fileId, long pathId)
{
    pointer["m_FileID"].AsInt = fileId;
    pointer["m_PathID"].AsLong = pathId;
}
