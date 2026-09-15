# Textures

A texture in Divinity II is a NIF file. Not a NIF that references an image —
the image *is* the file. It holds one `NiPersistentSrcTextureRendererData`
block and nothing else.

```
Flying_Froblin_A_DM.nif
  NiPersistentSrcTextureRendererData
    pixel_format  FMT_DXT5
    platform      DX9          renderer  XBOX360
    mipmaps       11           top       1024 x 1024
    pixel_data    1,398,128 bytes
```

## A mesh names a file that does not exist

`NiSourceTexture.file_name` says `Flying_Froblin_A_DM.tga`. There is no TGA in
the install. The file beside it is the same name with `.nif`, in
`Win32/Textures/`. The suffix in the NIF is what the artist exported, not what
shipped.

## The pixel data is already a DDS

The bytes in `pixel_data` are exactly what a DDS file carries, mip level after
mip level, in the order DDS expects. Only the 128-byte header is missing. Write
that header in front of the bytes and the result is a valid DDS that Blender
opens natively — no decoding, no re-compression, nothing lost.

The header needs the four-character code from `pixel_format`
(`FMT_DXT1`/`FMT_DXT3`/`FMT_DXT5` map to `DXT1`/`DXT3`/`DXT5`), the top
mipmap's width and height, and `num_mipmaps`.

Verified 2026-09-15: `Flying_Froblin_A_DM.nif` became 1,398,256 bytes of DDS
and Blender loaded it as 1024 x 1024, four channels.
