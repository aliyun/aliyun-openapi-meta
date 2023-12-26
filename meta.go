package aliyunopenapimeta

import (
	"embed"
)

//go:embed metadatas
//go:embed en-US
//go:embed zh-CN
var Metadatas embed.FS
