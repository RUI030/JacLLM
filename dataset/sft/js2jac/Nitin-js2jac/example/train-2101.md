# Record

```json
{
  "source": "code",
  "format": "jac",
  "class": "fullstack",
  "task_type": "js2jac",
  "fp": "thangdevalone__modern-ui::app/(docs-group)/docs/components/popover/preview.tsx",
  "origin_file": "js2jac_dataset_idiomatic.jsonl",
  "origin_id": "thangdevalone__modern-ui::app/(docs-group)/docs/components/popover/preview.tsx",
  "verification": "check",
  "n_tokens": 1709,
  "n_answer_tokens": 825
}
```

## SYSTEM

```
You are a helpful assistant.
```

## USER

Rewrite the following file in Jac, preserving semantics.
```ts
"use client";
import {RefreshCw} from 'lucide-react';
import {useState} from 'react';
import {Tabs, TabsContent, TabsList, TabsTrigger} from '@/components/modern-ui/tabs';
import {Button} from '@/components/modern-ui/button';
import {CodeBlock} from '@/components/code-block';
import {Popover, PopoverContent, PopoverTrigger} from '@/components/modern-ui/popover';

export const popoverCode = `import { Popover, PopoverTrigger, PopoverContent } from "@/components/modern-ui/popover";
import { Button } from "@/components/modern-ui/button";
            
export function PopoverDemo() {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button>Open Popover</Button>
      </PopoverTrigger>
      <PopoverContent className="w-80">
        <div className="grid gap-4">
          <div className="space-y-2">
            <h4 className="font-medium leading-none">Popover Title</h4>
            <p className="text-sm text-muted-foreground">
              This is a popover component with some example content.
            </p>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}`;

export const PreviewPopover = () => {
  const [activeTab, setActiveTab] = useState("preview");
  const [key, setKey] = useState(0);

  const handleRefresh = () => {
    setKey((prevKey) => prevKey + 1);
  };

  return (
    <>
      <Tabs value={activeTab} className="mb-8" onValueChange={(value) => setActiveTab(value)}>
        <TabsList>
          <TabsTrigger value="preview">Preview</TabsTrigger>
          <TabsTrigger value="code">Code</TabsTrigger>
        </TabsList>
        <TabsContent value="preview" className="p-6 border rounded-md mt-2 relative min-h-[300px]">
          <div className="absolute inset-0 bg-[radial-gradient(#80808080_1px,transparent_1px)] [background-size:16px_16px] opacity-50 ">
          </div>
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
            <Popover key={key}>
              <PopoverTrigger asChild>
                <Button>Open Popover</Button>
              </PopoverTrigger>
              <PopoverContent className="w-80">
                <div className="grid gap-4">
                  <div className="space-y-2">
                    <h4 className="font-medium leading-none">Popover Title</h4>
                    <p className="text-sm text-muted-foreground">
                      This is a popover component with some example content.
                    </p>
                  </div>
                </div>
              </PopoverContent>
            </Popover>
          </div>
          <div className="absolute z-10 top-4 right-4 flex gap-2">
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={handleRefresh}
            >
              <RefreshCw className="h-4 w-4"/>
            </Button>
          </div>
        </TabsContent>
        <TabsContent value="code" className="mt-2">
          <CodeBlock code={popoverCode} language={"tsx"} />
        </TabsContent>
      </Tabs>
    </>
  );
};
```

## ASSISTANT

import from "lucide-react" { RefreshCw }
import from "@/components/modern-ui/tabs" { Tabs, TabsContent, TabsList, TabsTrigger }
import from "@/components/modern-ui/button" { Button }
import from "@/components/code-block" { CodeBlock }
import from "@/components/modern-ui/popover" { Popover, PopoverContent, PopoverTrigger }

glob:pub popoverCode: str = f"import {{ Popover, PopoverTrigger, PopoverContent }} from \"@/components/modern-ui/popover\";\nimport {{ Button }} from \"@/components/modern-ui/button\";\n            \nexport function PopoverDemo() {{\n  return (\n    <Popover>\n      <PopoverTrigger asChild>\n        <Button>Open Popover</Button>\n      </PopoverTrigger>\n      <PopoverContent className=\"w-80\">\n        <div className=\"grid gap-4\">\n          <div className=\"space-y-2\">\n            <h4 className=\"font-medium leading-none\">Popover Title</h4>\n            <p className=\"text-sm text-muted-foreground\">\n              This is a popover component with some example content.\n            </p>\n          </div>\n        </div>\n      </PopoverContent>\n    </Popover>\n  );\n}}";

def:pub PreviewPopover() -> JsxElement {
    has activeTab: str = "preview";
    has key: int = 0;

    def handle_refresh(e: MouseEvent) {
        key = key + 1;
    }

    def handle_tab_change(value: str) {
        activeTab = value;
    }

    <Tabs value={activeTab} className="mb-8" onValueChange={handle_tab_change}>
        <TabsList>
            <TabsTrigger value="preview">Preview</TabsTrigger>
            <TabsTrigger value="code">Code</TabsTrigger>
        </TabsList>
        <TabsContent value="preview" className="p-6 border rounded-md mt-2 relative min-h-[300px]">
            <div className="absolute inset-0 bg-[radial-gradient(#80808080_1px,transparent_1px)] [background-size:16px_16px] opacity-50 "></div>
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
                <Popover key={key}>
                    <PopoverTrigger asChild>
                        <Button>Open Popover</Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-80">
                        <div className="grid gap-4">
                            <div className="space-y-2">
                                <h4 className="font-medium leading-none">Popover Title</h4>
                                <p className="text-sm text-muted-foreground">
                                    This is a popover component with some example content.
                                </p>
                            </div>
                        </div>
                    </PopoverContent>
                </Popover>
            </div>
            <div className="absolute z-10 top-4 right-4 flex gap-2">
                <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8"
                    onClick={handle_refresh}
                >
                    <RefreshCw className="h-4 w-4" />
                </Button>
            </div>
        </TabsContent>
        <TabsContent value="code" className="mt-2">
            <CodeBlock code={popoverCode} language="tsx" />
        </TabsContent>
    </Tabs>
}
