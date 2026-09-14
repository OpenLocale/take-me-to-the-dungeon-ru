using System;
using System.IO;
using System.Linq;
using TMPro;
using UnityEditor;
using UnityEngine;
using UnityEngine.TextCore.LowLevel;

public static class BuildCyrillicFont
{
    private const string SourceFontPath = "Assets/NotoSans-Regular.ttf";
    private const string CharactersPath = "Assets/cyrillic_chars.txt";
    private const string FontAssetPath = "Assets/CJKtc RU SDF.asset";
    private const string BundleName = "cjkru-sdf";

    public static void ImportEssentials()
    {
        TMP_PackageResourceImporter.ImportResources(true, false, false);
    }

    public static void Build()
    {
        try
        {
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            var sourceFont = AssetDatabase.LoadAssetAtPath<Font>(SourceFontPath);
            if (sourceFont == null)
                throw new InvalidOperationException("Noto Sans Regular source font was not imported");

            var characters = File.ReadAllText(Path.GetFullPath(CharactersPath));
            if (string.IsNullOrWhiteSpace(characters))
                throw new InvalidOperationException("The custom character set is empty");

            var fontAsset = TMP_FontAsset.CreateFontAsset(
                sourceFont,
                90,
                9,
                GlyphRenderMode.SDFAA_HINTED,
                2048,
                2048,
                AtlasPopulationMode.Dynamic,
                false);
            if (fontAsset == null)
                throw new InvalidOperationException("TMP_FontAsset.CreateFontAsset failed");

            fontAsset.name = "CJKtc RU SDF";
            fontAsset.material.name = "CJKtc RU SDF Material";
            fontAsset.atlasTextures[0].name = "CJKtc RU SDF Atlas";
            if (!fontAsset.TryAddCharacters(characters, out var missingCharacters, false))
            {
                var missing = string.Concat(missingCharacters.Distinct());
                throw new InvalidOperationException("Noto Sans Regular lacks required fallback characters: " + missing);
            }

            fontAsset.atlasPopulationMode = AtlasPopulationMode.Static;
            if (AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(FontAssetPath) != null &&
                !AssetDatabase.DeleteAsset(FontAssetPath))
                throw new InvalidOperationException("Existing TMP font asset could not be replaced");
            AssetDatabase.CreateAsset(fontAsset, FontAssetPath);
            AssetDatabase.AddObjectToAsset(fontAsset.material, fontAsset);
            foreach (var texture in fontAsset.atlasTextures)
                AssetDatabase.AddObjectToAsset(texture, fontAsset);

            EditorUtility.SetDirty(fontAsset);
            AssetDatabase.SaveAssets();

            var importer = AssetImporter.GetAtPath(FontAssetPath);
            importer.SetAssetBundleNameAndVariant(BundleName, string.Empty);
            AssetDatabase.SaveAssets();

            var output = Path.GetFullPath("FontBundle");
            Directory.CreateDirectory(output);
            var manifest = BuildPipeline.BuildAssetBundles(
                output,
                BuildAssetBundleOptions.UncompressedAssetBundle,
                BuildTarget.StandaloneWindows64);
            if (manifest == null || !File.Exists(Path.Combine(output, BundleName)))
                throw new InvalidOperationException("AssetBundle build failed");

            Debug.Log($"Built {BundleName} from Noto Sans/Regular with {characters.Distinct().Count()} characters");
            EditorApplication.Exit(0);
        }
        catch (Exception exception)
        {
            Debug.LogException(exception);
            EditorApplication.Exit(1);
        }
    }
}
