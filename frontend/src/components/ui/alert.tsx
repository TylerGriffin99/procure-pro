import { type HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import { AlertTriangle, Info, XCircle, CheckCircle } from "lucide-react";

const alertVariants = cva(
	"rounded-lg border p-4 flex items-start gap-3",
	{
		variants: {
			variant: {
				warning: "bg-warning/10 border-warning/30 text-warning-foreground",
				error: "bg-destructive/10 border-destructive/20 text-destructive",
				info: "bg-info/10 border-info/20 text-info",
				success: "bg-success/10 border-success/20 text-success",
			},
		},
		defaultVariants: {
			variant: "info",
		},
	}
);

const ALERT_ICONS = {
	warning: AlertTriangle,
	error: XCircle,
	info: Info,
	success: CheckCircle,
};

interface AlertProps
	extends HTMLAttributes<HTMLDivElement>,
		VariantProps<typeof alertVariants> {
	hideIcon?: boolean;
}

function Alert({ className, variant = "info", hideIcon, children, ...props }: AlertProps) {
	const Icon = ALERT_ICONS[variant!];

	return (
		<div className={cn(alertVariants({ variant }), className)} {...props}>
			{!hideIcon && <Icon className="h-5 w-5 shrink-0 mt-0.5" />}
			<div className="flex-1">{children}</div>
		</div>
	);
}

function AlertTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
	return <h3 className={cn("text-sm font-semibold", className)} {...props} />;
}

function AlertDescription({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
	return <div className={cn("text-sm mt-1", className)} {...props} />;
}

export { Alert, AlertTitle, AlertDescription };
