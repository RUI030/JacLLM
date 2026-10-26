# Record

```json
{
  "source": "code",
  "format": "jac",
  "class": "fullstack",
  "task_type": "js2jac",
  "fp": "shadcnspace__shadcnspace::components/shadcn-space/input/input-20.tsx",
  "origin_file": "js2jac_dataset_idiomatic.jsonl",
  "origin_id": "shadcnspace__shadcnspace::components/shadcn-space/input/input-20.tsx",
  "verification": "check",
  "n_tokens": 687,
  "n_answer_tokens": 310
}
```

## SYSTEM

```
You are an expert AI assistant specializing in the jac programming language.
```

## USER

Convert JS/TS → Jac. Reply with the full Jac source.
```ts
import { useId } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const RangeInputDemo = () => {
  const id = useId();
  return (
    <div className="*:not-first:mt-2">
      <Label className="flex-1">Range</Label>
      <div className="flex">
        <Input
          aria-label="Min Value"
          className="flex-1 rounded-e-none [-moz-appearance:textfield] focus:z-10 [&::-webkit-inner-spin-button]:m-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:m-0 [&::-webkit-outer-spin-button]:appearance-none"
          id={`${id}-1`}
          placeholder="From"
          type="number"
        />
        <Input
          aria-label="Max Value"
          className="-ms-px flex-1 rounded-s-none [-moz-appearance:textfield] focus:z-10 [&::-webkit-inner-spin-button]:m-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:m-0 [&::-webkit-outer-spin-button]:appearance-none"
          id={`${id}-2`}
          placeholder="To"
          type="number"
        />
      </div>
    </div>
  );
}

export default RangeInputDemo
```

## ASSISTANT

import from "react" { useId }
import from "@/components/ui/input" { Input }
import from "@/components/ui/label" { Label }

def:pub RangeInputDemo() -> JsxElement {
    id = useId();
    <div className="*:not-first:mt-2">
        <Label className="flex-1">Range</Label>
        <div className="flex">
            <Input
                aria-label="Min Value"
                className="flex-1 rounded-e-none [-moz-appearance:textfield] focus:z-10 [&::-webkit-inner-spin-button]:m-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:m-0 [&::-webkit-outer-spin-button]:appearance-none"
                id={f"{id}-1"}
                placeholder="From"
                type="number"
            />
            <Input
                aria-label="Max Value"
                className="-ms-px flex-1 rounded-s-none [-moz-appearance:textfield] focus:z-10 [&::-webkit-inner-spin-button]:m-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:m-0 [&::-webkit-outer-spin-button]:appearance-none"
                id={f"{id}-2"}
                placeholder="To"
                type="number"
            />
        </div>
    </div>
}
